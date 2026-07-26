"""Read use case for the paginated library book list."""

from src.application.library.queries.book_list import (
    BookListPageView,
    BookListQueryProtocol,
)
from src.domain.common.value_objects.ids import UserId


class GetBooksWithCountsUseCase:
    """Serve the library's book list with highlight and flashcard counts."""

    def __init__(self, book_list_query: BookListQueryProtocol) -> None:
        self.book_list_query = book_list_query

    async def get_books_with_counts(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 100,
        include_only_with_flashcards: bool = False,
        search_text: str | None = None,
    ) -> BookListPageView:
        """Return a page of the user's books ordered by title, plus the total."""
        return await self.book_list_query.list_books(
            user_id=UserId(user_id),
            offset=offset,
            limit=limit,
            include_only_with_flashcards=include_only_with_flashcards,
            search_text=search_text,
        )
