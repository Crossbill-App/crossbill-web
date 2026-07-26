"""Read use case for the in-book highlight search."""

from src.application.reading.queries.highlight_search import (
    BookHighlightSearchView,
    HighlightSearchQueryProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class HighlightSearchUseCase:
    """Serve full-text search within one book's highlights."""

    def __init__(self, highlight_search_query: HighlightSearchQueryProtocol) -> None:
        self.highlight_search_query = highlight_search_query

    async def search_book_highlights(
        self, book_id: int, user_id: int, search_text: str, limit: int = 100
    ) -> BookHighlightSearchView:
        """Return matching highlights grouped by chapter.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        view = await self.highlight_search_query.search_in_book(
            BookId(book_id), UserId(user_id), search_text, limit
        )
        if view is None:
            raise BookNotFoundError(book_id)
        return view
