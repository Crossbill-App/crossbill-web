"""API route for a book's aggregated reading statistics."""

from datetime import date, tzinfo
from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.reading.queries.get_book_statistics_use_case import (
    GetBookStatisticsUseCase,
)
from src.core import container
from src.domain.identity import User
from src.domain.reading.services.reading_activity_calculator import ReadingActivity
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.routers.reader_clock import reader_timezone, reader_today
from src.infrastructure.reading.schemas import (
    BookActivity,
    BookActivityDay,
    BookReadingStatistics,
)

router = APIRouter(prefix="/books", tags=["statistics"])


def _activity_schema(activity: ReadingActivity | None) -> BookActivity | None:
    """Convert the domain's activity grid into its response shape."""
    if activity is None:
        return None
    return BookActivity(
        unit=activity.unit.value,
        range_start=activity.range_start,
        range_end=activity.range_end,
        days=[
            BookActivityDay(date=day.day, value=day.value, level=day.level) for day in activity.days
        ],
    )


@router.get(
    "/{book_id}/statistics",
    response_model=BookReadingStatistics,
    status_code=status.HTTP_200_OK,
)
async def get_book_statistics(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    zone: Annotated[tzinfo, Depends(reader_timezone)],
    today: Annotated[date, Depends(reader_today)],
    use_case: GetBookStatisticsUseCase = Depends(
        inject_use_case(container.reading.get_book_statistics_use_case)
    ),
) -> BookReadingStatistics:
    """
    Get aggregated reading statistics for a specific book.

    Totals every reading session recorded for the book and reports how far
    through it the reader has got.

    Args:
        book_id: ID of the book
        tz: IANA timezone deciding which calendar day a session falls on

    Returns:
        BookReadingStatistics for the book
    """
    statistics = await use_case.get_statistics_for_book(
        book_id=book_id,
        user_id=current_user.id.value,
        today=today,
        zone=zone,
    )

    return BookReadingStatistics(
        session_count=statistics.session_count,
        total_reading_seconds=statistics.total_reading_seconds,
        average_session_seconds=statistics.average_session_seconds,
        first_session_start=statistics.first_session_start,
        last_session_end=statistics.last_session_end,
        span_days=statistics.span_days,
        progress_percent=statistics.progress_percent,
        activity=_activity_schema(statistics.activity),
    )
