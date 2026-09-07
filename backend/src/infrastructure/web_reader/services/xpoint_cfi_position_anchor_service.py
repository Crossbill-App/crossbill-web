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
from lxml.etree import _Element  # pyright: ignore[reportPrivateUsage]
from xpoint_cfi import css_selector as xpoint_css

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorMatch,
    AnchorResolutionError,
    AnchorSource,
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

# How much text to lift out of the document when a Locator brought none of its
# own. Long enough to name one place in a chapter without a second thought, short
# enough that it cannot run past the end of the paragraph it started in.
POINT_CONTEXT_CHARS = 120

# The best grade each kind of anchor can honestly come back with.
#
# A quote is graded on evidence the *caller* supplied, so it keeps whatever the
# library found. The other two are graded on a quote this module wrote itself
# out of the document -- which it will of course find again perfectly -- so the
# grade has to be capped at what the Locator's own evidence was worth: an
# element names exactly one place and nothing corroborates it (HIGHLIGHT_ONLY),
# and a progression is an approximation by construction (FUZZY).
_CONFIDENCE_CEILING = {
    AnchorSource.QUOTE: AnchorConfidence.BOTH_CONTEXTS,
    AnchorSource.ELEMENT: AnchorConfidence.HIGHLIGHT_ONLY,
    AnchorSource.PROGRESSION: AnchorConfidence.FUZZY,
}

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
        """Resolve a Locator back to the canonical ``XPointRange``, with a grade.

        A Locator carrying a text quote is resolved by that quote, which is the
        whole of what the library does. A Locator carrying **no text at all** is
        the ordinary shape of a reading position and would otherwise be
        unresolvable -- so a quote is *synthesised* from the document itself
        first, out of whatever the Locator did bring: the element its selector
        or fragment names, or failing that the text sitting at its progression.
        See :meth:`_anchored`.
        """
        book = await self._publication(ebook_file)
        anchored, source = self._anchored(book, locator)
        try:
            match = xpoint_cfi.locator_to_xpoint_range(book, _to_library_locator(anchored))
        except xpoint_cfi.XpointCfiError as exc:
            raise AnchorResolutionError(f"Cannot resolve locator {locator.href!r}: {exc}") from exc
        graded = _CONFIDENCE_BY_LIBRARY_MEMBER[match.confidence]
        return AnchorMatch(
            xpoints=XPointRange.parse(
                match.xpoint_range.start.to_string(), match.xpoint_range.end.to_string()
            ),
            # Capped, not reported raw: the library graded how well it found the
            # text *we* handed it, which for a synthesised quote is a measure of
            # our own copying rather than of how well the Locator said where it
            # was. The ceiling is what the Locator's own evidence supports.
            confidence=min(graded, _CONFIDENCE_CEILING[source]),
            anchored_by=source,
        )

    def verify_locator(self, locator: Locator, expected_text: str) -> bool:
        """Report whether a derived Locator covers the text that was stored.

        A Locator's ``text.highlight`` is read straight out of the EPUB when the
        Locator is built, so comparing it to the stored highlight text needs no
        second pass over the document.
        """
        normalize = xpoint_cfi.normalize_for_comparison
        return normalize(locator.text.highlight or "") == normalize(expected_text)

    # -- point anchoring ---------------------------------------------------------------

    def _anchored(self, book: xpoint_cfi.EpubMap, locator: Locator) -> tuple[Locator, AnchorSource]:
        """Give a text-less Locator something to anchor on, from the book itself.

        ``@readium/navigator`` reports a page turn from its column snapper's
        ``progress`` event, and the Locator it builds from that carries an
        ``href``, a ``position``, a ``progression`` -- and no text whatever. Fed
        to the library as it stands, every reading position in the world fails
        with *"no highlight and no context to anchor to"*. This is where that is
        answered.

        The synthesis is deliberately a *quote*, rather than a second way of
        computing an xpointer: text lifted verbatim out of the document is
        handed back through the same tested conversion the quote path uses, so
        there is one code path that turns a Locator into a position and one
        place for it to be wrong. What differs between the three cases is only
        where the text came from, and that is what :class:`AnchorSource`
        records.

        In order of how much the Locator actually pins down:

        1. **Its own text.** Left exactly as it came.
        2. **The element it names**, by CSS selector or fragment id. The quote
           is that element's first run of text, so the position lands where the
           element begins.
        3. **Its progression.** The quote is the text at that fraction of the
           resource, so the position lands about where the reader was.

        Raises:
            AnchorResolutionError: If the Locator names no resource of this
                book, or brought nothing at all to anchor on.
        """
        text = locator.text
        if text.before or text.highlight or text.after:
            return locator, AnchorSource.QUOTE

        node = self._document(book, locator.href)
        element = _named_element(node, locator.locations)
        if element is not None and (quote := _leading_run(element)):
            return _anchoring_on(locator, LocatorText(after=quote)), AnchorSource.ELEMENT

        at_progression = _text_at_progression(node, locator.locations.progression)
        if at_progression is not None:
            return _anchoring_on(locator, at_progression), AnchorSource.PROGRESSION

        raise AnchorResolutionError(
            f"Locator {locator.href!r} carries no text, no element and no progression"
        )

    def _document(self, book: xpoint_cfi.EpubMap, href: str) -> xpoint_cfi.NodeMap:
        """Return the parsed spine document a Locator's ``href`` names.

        Resolved through the library's own href matching rather than a second
        implementation of it. That is the point of reaching past the public
        surface here: the conversion that follows resolves the href again, and
        two rules for what ``href`` means could pick two different documents --
        quoting text out of one and then searching for it in the other.
        """
        try:
            spine_index = xpoint_cfi.locator._spine_index_for_href(book, href)  # pyright: ignore[reportPrivateUsage]
        except xpoint_cfi.XpointCfiError as exc:
            raise AnchorResolutionError(f"Cannot resolve locator {href!r}: {exc}") from exc
        return book.doc(spine_index)

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


def _anchoring_on(locator: Locator, text: LocatorText) -> Locator:
    """The same Locator, with a quote synthesised from the document put on it."""
    return Locator(href=locator.href, type=locator.type, locations=locator.locations, text=text)


def _named_element(node: xpoint_cfi.NodeMap, locations: LocatorLocations) -> _Element | None:
    """The one element a Locator names, by CSS selector or by fragment id.

    The selector is tried first: a navigator that supplies one derived it from
    the element it was actually looking at, while a fragment id may have come
    from a table-of-contents link the reader followed some pages ago.
    """
    if locations.css_selector:
        found = xpoint_css.resolve_selector(node.root, locations.css_selector)
        if found is not None:
            return found
    for fragment in locations.fragments:
        found = _element_by_id(node.root, fragment.lstrip("#"))
        if found is not None:
            return found
    return None


def _element_by_id(root: _Element, identifier: str) -> _Element | None:
    """The first element carrying ``id``, or ``None``.

    A scan rather than an XPath: the id comes from a request and building a
    query string out of it is a way to be surprised.
    """
    if not identifier:
        return None
    for element in root.iter():
        if element.get("id") == identifier:
            return element
    return None


def _leading_run(element: _Element) -> str | None:
    """The first run of real text under ``element``, capped, or ``None`` if it has none.

    One run, never a concatenation of several: text extraction puts a newline
    between block elements, so two runs joined here would be a string the
    document does not contain and the search for it would fail.
    """
    for chunk in element.itertext():
        text = str(chunk)
        if text.strip():
            return text[:POINT_CONTEXT_CHARS]
    return None


def _text_at_progression(node: xpoint_cfi.NodeMap, progression: float | None) -> LocatorText | None:
    """A quote taken from wherever ``progression`` falls in the resource's text.

    Expressed as ``after`` -- text the position sits *in front of* -- because
    that is what a caret is. At the very end of a resource there is nothing
    after it, so the quote becomes ``before`` instead and the position sits at
    its end.

    ``None`` when there is no progression to go on, or the resource holds no
    text to quote.
    """
    if progression is None:
        return None
    full = node.extract_text(None, None)
    if not full.strip():
        return None
    offset = min(len(full), max(0, round(progression * len(full))))
    if following := _first_run(full[offset:]):
        return LocatorText(after=following[:POINT_CONTEXT_CHARS])
    if preceding := _last_run(full[:offset]):
        return LocatorText(before=preceding[-POINT_CONTEXT_CHARS:])
    return None


def _first_run(text: str) -> str | None:
    """The first newline-delimited run of ``text`` with anything real in it."""
    return next((run for run in text.split("\n") if run.strip()), None)


def _last_run(text: str) -> str | None:
    """The last newline-delimited run of ``text`` with anything real in it."""
    return next((run for run in reversed(text.split("\n")) if run.strip()), None)


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
