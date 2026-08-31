"""API route for a book's aggregated reading statistics."""

from datetime import UTC, tzinfo
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.application.reading.queries.get_book_statistics_use_case import (
    GetBookStatisticsUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.schemas import BookReadingStatistics

router = APIRouter(prefix="/books", tags=["statistics"])


def reader_timezone(
    tz: Annotated[
        str,
        Query(description="IANA timezone the reader's calendar days are counted in"),
    ] = "UTC",
) -> tzinfo:
    """Read the caller's timezone, falling back to UTC when this server cannot resolve it.

    An unknown zone name shifts a day boundary at worst -- it is not worth
    failing the page over, and the reader would have got UTC anyway. ``ZoneInfo``
    resolves a key against the filesystem, so a malformed one surfaces as an
    ``OSError`` as readily as a lookup failure.
    """
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return UTC


@router.get(
    "/{book_id}/statistics",
    response_model=BookReadingStatistics,
    status_code=status.HTTP_200_OK,
)
async def get_book_statistics(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    zone: Annotated[tzinfo, Depends(reader_timezone)],
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
    )
