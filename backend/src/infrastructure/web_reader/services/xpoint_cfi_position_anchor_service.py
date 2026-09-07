"""Position-anchor adapter: xpointers to Readium Locators, via ``xpoint-cfi``.

Implements ``PositionAnchorServiceProtocol`` and ``PublicationCacheProtocol``.
This module is the only place in the backend that imports ``xpoint_cfi``; its
types stop here and the application layer sees only ``src.application.
web_reader.anchors``.
"""

from __future__ import annotations

import logging
from collections import OrderedDict

import xpoint_cfi

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorMatch,
    AnchorResolutionError,
    Locator,
    LocatorLocations,
    LocatorText,
)
from src.domain.common.value_objects.xpoint import XPoint, XPointRange

logger = logging.getLogger(__name__)

# How many parsed publications to hold at once. A parsed EPUB is a full lxml tree
# per spine item, so this trades resident memory for parse time: the cache exists
# to make converting one book's whole highlight list cost one parse, not to keep
# a library warm. A handful covers the books a small deployment has open at once.
PARSED_PUBLICATION_CACHE_SIZE = 4

_CONFIDENCE_BY_LIBRARY_MEMBER = {
    xpoint_cfi.MatchConfidence.FUZZY: AnchorConfidence.FUZZY,
    xpoint_cfi.MatchConfidence.AMBIGUOUS: AnchorConfidence.AMBIGUOUS,
    xpoint_cfi.MatchConfidence.HIGHLIGHT_ONLY: AnchorConfidence.HIGHLIGHT_ONLY,
    xpoint_cfi.MatchConfidence.ONE_CONTEXT: AnchorConfidence.ONE_CONTEXT,
    xpoint_cfi.MatchConfidence.BOTH_CONTEXTS: AnchorConfidence.BOTH_CONTEXTS,
}


class XPointCfiPositionAnchorService:
    """Converts between stored xpointers and Readium Locators for one book at a time.

    Holds an LRU of parsed publications keyed by ``Book.ebook_file``. The key is
    reused when a book's EPUB is replaced, so :meth:`evict` must be called on
    that path -- see ``PublicationCacheProtocol``.

    The instance is process-wide (a DI singleton), which is what makes the cache
    worth having; it is not safe to share across processes and does not need to
    be. Two concurrent misses for the same book parse twice and the later one
    wins, which costs a parse and nothing else.
    """

    def __init__(self, file_repository: FileRepositoryProtocol) -> None:
        """Initialize with the store the EPUB bytes are read from.

        Args:
            file_repository: Where ``ebook_file`` names are resolved to bytes.
        """
        self.file_repository = file_repository
        self._publications: OrderedDict[str, xpoint_cfi.EpubMap] = OrderedDict()

    # -- PositionAnchorServiceProtocol -------------------------------------------------

    async def locator_for_xpoint(self, ebook_file: str, xpoint: XPoint) -> Locator:
        """Derive a Locator for a single position."""
        book = await self._publication(ebook_file)
        try:
            locator = xpoint_cfi.xpoint_to_locator(book, xpoint.to_string())
        except xpoint_cfi.XpointCfiError as exc:
            raise AnchorResolutionError(f"Cannot locate {xpoint.to_string()!r}: {exc}") from exc
        return _to_locator(locator)

    async def locator_for_xpoint_range(self, ebook_file: str, xpoints: XPointRange) -> Locator:
        """Derive a Locator for a highlight's range."""
        book = await self._publication(ebook_file)
        start, end = xpoints.start.to_string(), xpoints.end.to_string()
        try:
            locator = xpoint_cfi.xpoint_range_to_locator(book, start, end)
        except xpoint_cfi.XpointCfiError as exc:
            raise AnchorResolutionError(f"Cannot locate {start!r}..{end!r}: {exc}") from exc
        return _to_locator(locator)

    async def xpoint_range_for_locator(self, ebook_file: str, locator: Locator) -> AnchorMatch:
        """Resolve a Locator back to the canonical ``XPointRange``, with a grade."""
        book = await self._publication(ebook_file)
        try:
            match = xpoint_cfi.locator_to_xpoint_range(book, _to_library_locator(locator))
        except xpoint_cfi.XpointCfiError as exc:
            raise AnchorResolutionError(f"Cannot resolve locator {locator.href!r}: {exc}") from exc
        return AnchorMatch(
            xpoints=XPointRange.parse(
                match.xpoint_range.start.to_string(), match.xpoint_range.end.to_string()
            ),
            confidence=_CONFIDENCE_BY_LIBRARY_MEMBER[match.confidence],
        )

    def verify_locator(self, locator: Locator, expected_text: str) -> bool:
        """Report whether a derived Locator covers the text that was stored.

        A Locator's ``text.highlight`` is read straight out of the EPUB when the
        Locator is built, so comparing it to the stored highlight text needs no
        second pass over the document.
        """
        normalize = xpoint_cfi.normalize_for_comparison
        return normalize(locator.text.highlight or "") == normalize(expected_text)

    # -- PublicationCacheProtocol ------------------------------------------------------

    def evict(self, ebook_file: str) -> None:
        """Drop any parsed publication cached for ``ebook_file``."""
        if self._publications.pop(ebook_file, None) is not None:
            logger.debug("Evicted parsed publication for %s", ebook_file)

    # -- internals ---------------------------------------------------------------------

    async def _publication(self, ebook_file: str) -> xpoint_cfi.EpubMap:
        """Return the parsed publication for ``ebook_file``, parsing it on a miss."""
        cached = self._publications.get(ebook_file)
        if cached is not None:
            self._publications.move_to_end(ebook_file)
            return cached

        content = await self.file_repository.get_epub(ebook_file)
        if content is None:
            raise AnchorResolutionError(f"No EPUB stored for {ebook_file!r}")
        try:
            book = xpoint_cfi.EpubMap.from_bytes(content)
        except xpoint_cfi.XpointCfiError as exc:
            raise AnchorResolutionError(f"Cannot parse EPUB {ebook_file!r}: {exc}") from exc

        self._publications[ebook_file] = book
        if len(self._publications) > PARSED_PUBLICATION_CACHE_SIZE:
            self._publications.popitem(last=False)
        return book


def _to_locator(locator: xpoint_cfi.Locator) -> Locator:
    """Translate the library's Locator into the application-layer one."""
    return Locator(
        href=locator.href,
        type=locator.type,
        locations=LocatorLocations(
            progression=locator.locations.progression,
            css_selector=locator.locations.css_selector,
        ),
        text=LocatorText(
            before=locator.text.before,
            highlight=locator.text.highlight,
            after=locator.text.after,
        ),
    )


def _to_library_locator(locator: Locator) -> xpoint_cfi.Locator:
    """Translate an application-layer Locator into the library's."""
    return xpoint_cfi.Locator(
        href=locator.href,
        type=locator.type,
        locations=xpoint_cfi.LocatorLocations(
            progression=locator.locations.progression,
            css_selector=locator.locations.css_selector,
        ),
        text=xpoint_cfi.LocatorText(
            before=locator.text.before,
            highlight=locator.text.highlight,
            after=locator.text.after,
        ),
    )
