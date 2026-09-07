"""Read use case behind the Web Publication Manifest endpoint."""

from src.application.web_reader.publications import ParsedPublication
from src.application.web_reader.queries.web_publication import WebPublicationQueryProtocol
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetWebPublicationUseCase:
    """Serve one book's publication structure to the web reader."""

    def __init__(self, web_publication_query: WebPublicationQueryProtocol) -> None:
        self.web_publication_query = web_publication_query

    async def get_web_publication(self, book_id: int, user_id: int) -> ParsedPublication:
        """Return the publication the manifest renders.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no stored EPUB to read.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        publication = await self.web_publication_query.get_web_publication(
            BookId(book_id), UserId(user_id)
        )
        if publication is None:
            raise BookNotFoundError(book_id)
        return publication
