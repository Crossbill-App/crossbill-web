"""API route for the reader's whole library on one activity grid."""

from datetime import date, tzinfo
from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.reading.queries.get_library_reading_activity_use_case import (
    GetLibraryReadingActivityUseCase,
)
from src.application.reading.queries.library_reading_activity import (
    LibraryReadingActivityView,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.routers.reader_clock import reader_timezone, reader_today
from src.infrastructure.reading.schemas import (
    ActivityBook,
    LibraryActivity,
    LibraryActivityDay,
    LibraryReadingActivityResponse,
)

router = APIRouter(prefix="/statistics", tags=["statistics"])


def _activity_schema(view: LibraryReadingActivityView | None) -> LibraryActivity | None:
    """Convert the read model's grid and titles into their response shape."""
    if view is None:
        return None

    activity = view.activity
    return LibraryActivity(
        unit=activity.unit.value,
        range_start=activity.range_start,
        range_end=activity.range_end,
        days=[
            LibraryActivityDay(
                date=day.day,
                value=day.value,
                level=day.level,
                book_ids=[book_id.value for book_id in day.book_ids],
            )
            for day in activity.days
        ],
        books=[
            ActivityBook(id=book_id.value, title=title) for book_id, title in view.titles.items()
        ],
    )


@router.get(
    "/reading-activity",
    response_model=LibraryReadingActivityResponse,
    status_code=status.HTTP_200_OK,
)
async def get_library_reading_activity(
    current_user: Annotated[User, Depends(get_current_user)],
    zone: Annotated[tzinfo, Depends(reader_timezone)],
    today: Annotated[date, Depends(reader_today)],
    use_case: GetLibraryReadingActivityUseCase = Depends(
        inject_use_case(container.reading.get_library_reading_activity_use_case)
    ),
) -> LibraryReadingActivityResponse:
    """
    Get the reader's daily reading activity across every book.

    Colours one square per day by how much of the library was read that day,
    and names the books each day was spent on.

    Args:
        tz: IANA timezone deciding which calendar day a session falls on

    Returns:
        LibraryReadingActivityResponse for the whole library
    """
    view = await use_case.get_activity(
        user_id=current_user.id.value,
        today=today,
        zone=zone,
    )

    return LibraryReadingActivityResponse(activity=_activity_schema(view))
