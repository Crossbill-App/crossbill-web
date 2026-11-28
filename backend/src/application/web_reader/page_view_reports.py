"""Placing the Page Views the Web Reader reports with each reading position."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog

from src.application.reading.page_view_placement import place_page_view
from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorMatch,
    AnchorResolutionError,
    AnchorSource,
    Locator,
)
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.domain.common.value_objects import BookId
from src.domain.common.value_objects.position_index import PositionIndex
from src.domain.reading.value_objects.page_view import PageView

logger = structlog.get_logger(__name__)

# No progression: a Page View is counted in characters, which a progression only
# approximates (ADR-0004, Amendment 9).
MINIMUM_PAGE_VIEW_CONFIDENCE = {
    AnchorSource.QUOTE: AnchorConfidence.HIGHLIGHT_ONLY,
    AnchorSource.ELEMENT: AnchorConfidence.HIGHLIGHT_ONLY,
}


@dataclass(frozen=True)
class PageViewReport:
    """One screen the Web Reader showed: quotes of its first and last words, and when."""

    start: Locator
    end: Locator
    shown_ms_before_send: int
    duration_ms: int


class _UnplaceableError(Exception):
    pass


async def placed_page_views(
    anchor_service: PositionAnchorServiceProtocol,
    book_id: BookId,
    epub_content: bytes,
    position_index: PositionIndex,
    source_hash: str,
    now: datetime,
    reports: list[PageViewReport],
) -> list[PageView]:
    """The reported Page Views placed in the book; one that cannot be placed is dropped and logged."""
    if not reports:
        return []
    edges = [edge for report in reports for edge in (report.start, report.end)]
    try:
        matches = await anchor_service.xpoint_ranges_for_locators(
            epub_content, dict(enumerate(edges))
        )
    except AnchorResolutionError as exc:
        logger.warning(
            "dropping_page_views", book_id=book_id.value, count=len(reports), reason=str(exc)
        )
        return []
    placed: list[PageView] = []
    for n, report in enumerate(reports):
        try:
            start, end = matches[2 * n], matches[2 * n + 1]
            placed.append(_page_view(report, start, end, position_index, source_hash, now))
        except _UnplaceableError as exc:
            logger.warning("dropping_page_view", book_id=book_id.value, reason=str(exc))
    return placed


def _firmly_anchored(match: AnchorMatch | None) -> AnchorMatch:
    if match is None:
        raise _UnplaceableError("not_in_book")
    floor = MINIMUM_PAGE_VIEW_CONFIDENCE.get(match.anchored_by)
    if floor is None:
        raise _UnplaceableError(f"anchored_by_{match.anchored_by.value}")
    if match.confidence < floor:
        raise _UnplaceableError("weak_anchor")
    return match


def _page_view(
    report: PageViewReport,
    start: AnchorMatch | None,
    end: AnchorMatch | None,
    position_index: PositionIndex,
    source_hash: str,
    now: datetime,
) -> PageView:
    first_words = _firmly_anchored(start).xpoints.start
    last_words = _firmly_anchored(end).xpoints.end
    if report.shown_ms_before_send < 0:
        raise _UnplaceableError("shown_after_send")
    try:
        shown_at = now - timedelta(milliseconds=report.shown_ms_before_send)
        duration = timedelta(milliseconds=report.duration_ms)
    except OverflowError as exc:
        raise _UnplaceableError("time_out_of_range") from exc
    page_view = place_page_view(
        position_index,
        first_words.to_string(),
        last_words.to_string(),
        source_hash,
        shown_at=shown_at,
        duration=duration,
    )
    if page_view is None:
        raise _UnplaceableError("unplaceable")
    return page_view
