"""Read use case for the recently-synced book list."""

from src.application.library.queries.book_list import (
    BookListQueryProtocol,
    BookWithCountsView,
)
from src.domain.common.value_objects.ids import UserId


class GetRecentlySyncedBooksUseCase:
    """Serve the books a device has sent data for, most recently synced first."""

    def __init__(self, book_list_query: BookListQueryProtocol) -> None:
        self.book_list_query = book_list_query

    async def get_recently_synced(
        self, user_id: int, limit: int = 10
    ) -> tuple[BookWithCountsView, ...]:
        """Return the user's recently synced books with their counts."""
        return await self.book_list_query.list_recently_synced(
            user_id=UserId(user_id),
            limit=limit,
        )
