"""Read use case for the reader's whole library on one activity grid."""

from datetime import date, tzinfo

from src.application.reading.queries.library_reading_activity import (
    LibraryReadingActivityQueryProtocol,
    LibraryReadingActivityView,
)
from src.domain.common.value_objects import UserId


class GetLibraryReadingActivityUseCase:
    """Serve every book's reading, day by day, on one grid."""

    def __init__(self, library_reading_activity_query: LibraryReadingActivityQueryProtocol) -> None:
        self.library_reading_activity_query = library_reading_activity_query

    async def get_activity(
        self, user_id: int, today: date, zone: tzinfo
    ) -> LibraryReadingActivityView | None:
        """Return the reader's activity grid, or ``None`` when there is none to draw."""
        return await self.library_reading_activity_query.get_activity(UserId(user_id), today, zone)
