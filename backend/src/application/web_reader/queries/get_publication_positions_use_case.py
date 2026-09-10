"""Read model for the position list the manifest's ``position-list`` link points at."""

from src.application.web_reader.queries.get_publication_use_case import GetPublicationUseCase
from src.application.web_reader.queries.publication_positions import (
    PublicationPosition,
    position_list,
)


class GetPublicationPositionsUseCase:
    """Cut one book's publication into the positions a Locator can name."""

    def __init__(self, get_publication_use_case: GetPublicationUseCase) -> None:
        self.get_publication_use_case = get_publication_use_case

    async def get_publication_positions(
        self, book_id: int, user_id: int
    ) -> tuple[PublicationPosition, ...]:
        """Return every position of the publication the manifest renders.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no stored EPUB to derive from.
            InvalidEbookError: If that EPUB cannot be parsed, or declares more
                positions than a publication may hold.
        """
        publication = await self.get_publication_use_case.get_publication(
            book_id=book_id,
            user_id=user_id,
        )
        return position_list(publication.reading_order)
