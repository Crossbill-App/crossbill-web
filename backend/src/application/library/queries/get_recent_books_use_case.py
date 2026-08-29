"""Read use case for the recent-books list."""

from src.application.library.queries.book_list import (
    BookListQueryProtocol,
    BookWithCountsView,
)
from src.domain.common.value_objects.ids import UserId


class GetRecentBooksUseCase:
    """Serve the books the user last opened or a device last synced."""

    def __init__(self, book_list_query: BookListQueryProtocol) -> None:
        self.book_list_query = book_list_query

    async def get_recent(self, user_id: int, limit: int = 10) -> tuple[BookWithCountsView, ...]:
        """Return the user's most recently touched books with their counts."""
        return await self.book_list_query.list_recent(
            user_id=UserId(user_id),
            limit=limit,
        )
