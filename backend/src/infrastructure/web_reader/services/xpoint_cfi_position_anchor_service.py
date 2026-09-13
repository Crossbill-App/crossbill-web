"""Position-anchor adapter: stored xpointers to Readium Locators and back, via ``xpoint-cfi``.

This module is the only place in the backend that imports ``xpoint_cfi``; its
types stop here and the application layer sees only
``src.application.web_reader.anchors``.
"""

import asyncio
import zipfile
import zlib
from collections.abc import Callable, Hashable, Mapping
from math import isfinite

import structlog
import xpoint_cfi
from lxml.etree import _Element  # pyright: ignore[reportPrivateUsage]
from xpoint_cfi import css_selector as xpoint_css

from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorMatch,
    AnchorNotFoundError,
    AnchorResolutionError,
    AnchorSource,
    Locator,
    LocatorLocations,
    LocatorText,
)
from src.domain.common.value_objects.xpoint import XPoint, XPointRange

logger = structlog.get_logger(__name__)

# ``xpoint_cfi`` reads spine documents through ``zipfile`` as it goes, so a broken
# archive surfaces here rather than at construction -- as ``read_bounded_member`` sees it too.
UNREADABLE_ARCHIVE = (OSError, zipfile.BadZipFile, EOFError, zlib.error)

POINT_CONTEXT_CHARS = 120

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
    """Converts one book's positions in either direction, each call against one parse."""

    async def locators_for_xpoint_ranges[K: Hashable](
        self, epub_content: bytes, ranges: Mapping[K, XPointRange]
    ) -> dict[K, Locator | None]:
        """Derive a Locator per range, or ``None`` where that range does not resolve."""
        if not ranges:
            return {}
        return await asyncio.to_thread(_converted, epub_content, ranges, _range_to_locator)

    async def locators_for_xpoints[K: Hashable](
        self, epub_content: bytes, points: Mapping[K, XPoint]
    ) -> dict[K, Locator | None]:
        """Derive a caret Locator per position, or ``None`` where one does not resolve."""
        if not points:
            return {}
        return await asyncio.to_thread(_converted, epub_content, points, _point_to_locator)

    async def xpoint_range_for_locator(self, epub_content: bytes, locator: Locator) -> AnchorMatch:
        """Resolve one browser-made Locator back to the canonical coordinates."""
        return await asyncio.to_thread(_resolved, epub_content, locator)

    def verify_locator(self, locator: Locator, expected_text: str) -> bool:
        """Report whether a Locator's quote is the text that was stored."""
        normalize = xpoint_cfi.normalize_for_comparison
        return normalize(locator.text.highlight or "") == normalize(expected_text)


def _converted[K: Hashable, P](
    epub_content: bytes,
    positions: Mapping[K, P],
    to_locator: Callable[[xpoint_cfi.EpubMap, P], xpoint_cfi.Locator],
) -> dict[K, Locator | None]:
    """Parse the EPUB and convert every position, all on one worker thread.

    The parse and the whole loop are one hop rather than one per position: a
    conversion is pure lxml CPU with no await in it, and a book's positions add
    up to hundreds of milliseconds (ADR-0004, *Amendment 5*) that the event loop
    would charge to every other request in the process.
    """
    book = _parsed(epub_content)

    converted: dict[K, Locator | None] = {}
    for key, position in positions.items():
        try:
            converted[key] = _to_locator(to_locator(book, position))
        except (xpoint_cfi.XpointCfiError, *UNREADABLE_ARCHIVE) as exc:
            logger.info("unresolvable_anchor", anchor_key=key, reason=str(exc))
            converted[key] = None
    return converted


def _resolved(epub_content: bytes, locator: Locator) -> AnchorMatch:
    book = _parsed(epub_content)
    try:
        anchored, source = _anchored(book, locator)
        match = xpoint_cfi.locator_to_xpoint_range(book, _to_library_locator(anchored))
    # A document that cannot be parsed fails every locator into it together, which is the
    # archive's failure rather than this Locator's; it must be caught before its base class.
    except (xpoint_cfi.EpubStructureError, *UNREADABLE_ARCHIVE) as exc:
        raise AnchorResolutionError(f"Cannot read EPUB: {exc}") from exc
    except xpoint_cfi.XpointCfiError as exc:
        raise AnchorNotFoundError(f"Cannot place locator {locator.href!r}: {exc}") from exc

    return AnchorMatch(
        xpoints=XPointRange.parse(
            match.xpoint_range.start.to_string(), match.xpoint_range.end.to_string()
        ),
        confidence=min(
            _CONFIDENCE_BY_LIBRARY_MEMBER[match.confidence], _CONFIDENCE_CEILING[source]
        ),
        anchored_by=source,
    )


def _anchored(book: xpoint_cfi.EpubMap, locator: Locator) -> tuple[Locator, AnchorSource]:
    text = locator.text
    quoted = (text.before, text.highlight, text.after)
    if any(xpoint_cfi.normalize_for_comparison(part or "") for part in quoted):
        return locator, AnchorSource.QUOTE

    node = _document(book, locator.href)
    element = _named_element(node, locator.locations)
    if element is not None and (quote := _leading_run(element)):
        return _anchoring_on(locator, LocatorText(after=quote)), AnchorSource.ELEMENT

    if quote := _text_at_progression(node, locator.locations.progression):
        return _anchoring_on(locator, quote), AnchorSource.PROGRESSION

    raise AnchorNotFoundError(
        f"Locator {locator.href!r} carries no usable text, element, or progression"
    )


def _document(book: xpoint_cfi.EpubMap, href: str) -> xpoint_cfi.NodeMap:
    try:
        spine_index = xpoint_cfi.locator._spine_index_for_href(  # pyright: ignore[reportPrivateUsage]
            book, href
        )
    except xpoint_cfi.XpointCfiError as exc:
        raise AnchorNotFoundError(f"Cannot place locator {href!r}: {exc}") from exc
    return book.doc(spine_index)


def _anchoring_on(locator: Locator, text: LocatorText) -> Locator:
    return Locator(href=locator.href, type=locator.type, locations=locator.locations, text=text)


def _named_element(node: xpoint_cfi.NodeMap, locations: LocatorLocations) -> _Element | None:
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
    if not identifier:
        return None
    return next((element for element in root.iter() if element.get("id") == identifier), None)


def _leading_run(element: _Element) -> str | None:
    # Leading whitespace is markup indentation the library's scope search will not find;
    # trailing whitespace is real separator text that disambiguates the quote, so it stays.
    for chunk in element.itertext():
        text = str(chunk)
        if text.strip():
            return text.lstrip()[:POINT_CONTEXT_CHARS]
    return None


def _text_at_progression(node: xpoint_cfi.NodeMap, progression: float | None) -> LocatorText | None:
    # Always ``after``, never ``before``: a point anchor carrying only ``before`` resolves to
    # the start of the enclosing element whatever text it names, so the last run past the
    # offset is what places the end of a resource -- one field, and one way to be wrong.
    if progression is None or not isfinite(progression):
        return None
    full = node.extract_text(None, None)
    if not full.strip():
        return None
    offset = round(min(1.0, max(0.0, progression)) * len(full))
    run = _first_run(full[offset:]) or _last_run(full[:offset])
    return LocatorText(after=run[:POINT_CONTEXT_CHARS]) if run else None


def _first_run(text: str) -> str | None:
    return next((run for run in text.split("\n") if run.strip()), None)


def _last_run(text: str) -> str | None:
    return next((run for run in reversed(text.split("\n")) if run.strip()), None)


def _parsed(epub_content: bytes) -> xpoint_cfi.EpubMap:
    try:
        return xpoint_cfi.EpubMap.from_bytes(epub_content)
    except (xpoint_cfi.XpointCfiError, *UNREADABLE_ARCHIVE) as exc:
        raise AnchorResolutionError(f"Cannot read EPUB: {exc}") from exc


def _range_to_locator(book: xpoint_cfi.EpubMap, xpoints: XPointRange) -> xpoint_cfi.Locator:
    return xpoint_cfi.xpoint_range_to_locator(
        book, xpoints.start.to_string(), xpoints.end.to_string()
    )


def _point_to_locator(book: xpoint_cfi.EpubMap, point: XPoint) -> xpoint_cfi.Locator:
    return xpoint_cfi.xpoint_to_locator(book, point.to_string())


def _to_locator(locator: xpoint_cfi.Locator) -> Locator:
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
