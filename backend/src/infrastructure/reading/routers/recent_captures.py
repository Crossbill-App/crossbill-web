"""API route for the reader's latest highlights and notes across every book."""

from datetime import tzinfo
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.application.reading.queries.get_recent_captures_use_case import GetRecentCapturesUseCase
from src.application.reading.queries.recent_captures import RecentCaptureView
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas.response_wrappers import CollectionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.routers.reader_clock import reader_timezone
from src.infrastructure.reading.schemas import HighlightLabel, RecentCapture

router = APIRouter(prefix="/captures", tags=["captures"])


def _capture_schema(view: RecentCaptureView) -> RecentCapture:
    """Convert one capture from the read model into its response shape."""
    return RecentCapture(
        kind=view.kind.value,
        id=view.id,
        book_id=view.book_id,
        book_title=view.book_title,
        chapter_name=view.chapter_name,
        title=view.title,
        text=view.text,
        note_kind=view.note_kind,
        page=view.page,
        label=HighlightLabel(
            highlight_style_id=view.label.highlight_style_id,
            text=view.label.text,
            ui_color=view.label.ui_color,
        )
        if view.label
        else None,
        captured_at=view.captured_at,
        day=view.day,
        more_in_book=view.more_in_book,
    )


@router.get(
    "/recent",
    response_model=CollectionResponse[RecentCapture],
    status_code=status.HTTP_200_OK,
)
async def get_recent_captures(
    current_user: Annotated[User, Depends(get_current_user)],
    zone: Annotated[tzinfo, Depends(reader_timezone)],
    use_case: GetRecentCapturesUseCase = Depends(
        inject_use_case(container.reading.get_recent_captures_use_case)
    ),
    limit: int = Query(8, ge=1, le=50, description="Maximum number of captures to return"),
) -> CollectionResponse[RecentCapture]:
    """
    Get the reader's most recent highlights and notes, newest first.

    A highlight is filed under the moment the e-reader recorded it; a note
    under its latest edit. One book contributes at most three captures to any
    one day, and the last of those says how many more that day holds.

    Args:
        tz: IANA timezone deciding which calendar day a note falls on
        limit: Maximum number of captures to return (default: 8, max: 50)

    Returns:
        CollectionResponse with the captures, newest first
    """
    captures = await use_case.get_recent_captures(current_user.id.value, zone, limit)

    return CollectionResponse[RecentCapture](
        items=[_capture_schema(capture) for capture in captures]
    )
