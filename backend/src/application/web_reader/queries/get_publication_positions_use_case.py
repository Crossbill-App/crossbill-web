"""Read use case behind the publication position-list endpoint."""

from src.application.web_reader.queries.publication_positions import (
    PublicationPosition,
    PublicationPositionsQueryProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetPublicationPositionsUseCase:
    """Serve one book's position list to the web reader."""

    def __init__(self, publication_positions_query: PublicationPositionsQueryProtocol) -> None:
        self.publication_positions_query = publication_positions_query

    async def get_publication_positions(
        self, book_id: int, user_id: int
    ) -> tuple[PublicationPosition, ...]:
        """Return every position of the book's publication, in reading order.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no stored EPUB to read.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        positions = await self.publication_positions_query.get_publication_positions(
            BookId(book_id), UserId(user_id)
        )
        if positions is None:
            raise BookNotFoundError(book_id)
        return positions
