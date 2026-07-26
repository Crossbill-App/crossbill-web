"""Read use case for a book's highlight-label list."""

from src.application.reading.queries.highlight_labels import (
    HighlightLabelQueryProtocol,
    HighlightLabelView,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetBookHighlightLabelsUseCase:
    """Serve a book's highlight labels with their resolved text and counts."""

    def __init__(self, highlight_label_query: HighlightLabelQueryProtocol) -> None:
        self.highlight_label_query = highlight_label_query

    async def execute(self, book_id: int, user_id: int) -> tuple[HighlightLabelView, ...]:
        """Return the book's labels.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        labels = await self.highlight_label_query.list_for_book(BookId(book_id), UserId(user_id))
        if labels is None:
            raise BookNotFoundError(book_id)
        return labels
