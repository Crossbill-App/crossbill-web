"""Read use case for a book's stored highlight locators."""

from src.application.web_reader.queries.highlight_locators import (
    HighlightLocatorQueryProtocol,
    HighlightLocatorView,
    locator_view,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetBookHighlightLocatorsUseCase:
    """Answer where every live highlight of one book is, or why it cannot be said."""

    def __init__(self, highlight_locator_query: HighlightLocatorQueryProtocol) -> None:
        self.highlight_locator_query = highlight_locator_query

    async def get_book_highlight_locators(
        self, book_id: BookId, user_id: UserId
    ) -> list[HighlightLocatorView]:
        """Return one entry per live highlight of the book, in highlight-id order.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        stored = await self.highlight_locator_query.locators_for_book(book_id, user_id)
        if stored is None:
            raise BookNotFoundError(book_id.value)
        return [locator_view(row, stored.publication_hash) for row in stored.highlights]
