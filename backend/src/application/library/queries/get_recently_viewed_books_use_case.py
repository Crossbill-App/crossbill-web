"""Read use case for the recently-viewed book list."""

from src.application.library.queries.book_list import (
    BookListQueryProtocol,
    BookWithCountsView,
)
from src.domain.common.value_objects.ids import UserId


class GetRecentlyViewedBooksUseCase:
    """Serve the books the user has opened, most recently viewed first."""

    def __init__(self, book_list_query: BookListQueryProtocol) -> None:
        self.book_list_query = book_list_query

    async def get_recently_viewed(
        self, user_id: int, limit: int = 10
    ) -> tuple[BookWithCountsView, ...]:
        """Return the user's recently viewed books with their counts."""
        return await self.book_list_query.list_recently_viewed(
            user_id=UserId(user_id),
            limit=limit,
        )
