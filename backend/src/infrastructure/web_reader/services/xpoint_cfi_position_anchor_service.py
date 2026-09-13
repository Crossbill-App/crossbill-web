"""Position-anchor adapter: stored xpointers to Readium Locators, via ``xpoint-cfi``.

This module is the only place in the backend that imports ``xpoint_cfi``; its
types stop here and the application layer sees only
``src.application.web_reader.anchors``.
"""

import asyncio
import zipfile
import zlib
from collections.abc import Callable, Hashable, Mapping

import structlog
import xpoint_cfi

from src.application.web_reader.anchors import (
    AnchorResolutionError,
    Locator,
    LocatorLocations,
    LocatorText,
)
from src.domain.common.value_objects.xpoint import XPoint, XPointRange

logger = structlog.get_logger(__name__)

# ``xpoint_cfi`` reads spine documents through ``zipfile`` as it goes, so a broken
# archive surfaces here rather than at construction -- as ``read_bounded_member`` sees it too.
UNREADABLE_ARCHIVE = (OSError, zipfile.BadZipFile, EOFError, zlib.error)


class XPointCfiPositionAnchorService:
    """Converts a batch of one book's stored positions against a single EPUB parse."""

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
    try:
        book = xpoint_cfi.EpubMap.from_bytes(epub_content)
    except (xpoint_cfi.XpointCfiError, *UNREADABLE_ARCHIVE) as exc:
        raise AnchorResolutionError(f"Cannot read EPUB: {exc}") from exc

    converted: dict[K, Locator | None] = {}
    for key, position in positions.items():
        try:
            converted[key] = _to_locator(to_locator(book, position))
        except (xpoint_cfi.XpointCfiError, *UNREADABLE_ARCHIVE) as exc:
            logger.info("unresolvable_anchor", anchor_key=key, reason=str(exc))
            converted[key] = None
    return converted


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
