"""Read use case for the ereader's highlight list."""

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.queries.ereader_highlights import (
    EreaderHighlightsQueryProtocol,
    EreaderHighlightView,
)
from src.domain.common.value_objects.ids import UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetEreaderBookHighlightsUseCase:
    """Serve a book's highlights to the device that identifies it by client id."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        ereader_highlights_query: EreaderHighlightsQueryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.ereader_highlights_query = ereader_highlights_query

    async def get_highlights_for_client_book(
        self, client_book_id: str, user_id: UserId
    ) -> tuple[EreaderHighlightView, ...]:
        """Get every live highlight of the book, in reading order.

        Raises:
            BookNotFoundError: If no book matches client_book_id for the user.
        """
        book = await self.book_repository.find_by_client_book_id(client_book_id, user_id)
        if book is None:
            raise BookNotFoundError(client_book_id)
        return await self.ereader_highlights_query.list_for_book(book.id, user_id)
