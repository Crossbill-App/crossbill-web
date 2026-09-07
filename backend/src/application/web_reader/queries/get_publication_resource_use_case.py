"""Read use case behind the publication resource endpoint."""

from src.application.web_reader.queries.publication_resource import (
    PublicationResourceQueryProtocol,
    PublicationResourceView,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetPublicationResourceUseCase:
    """Serve one file of a book's publication to the web reader."""

    def __init__(self, publication_resource_query: PublicationResourceQueryProtocol) -> None:
        self.publication_resource_query = publication_resource_query

    async def get_publication_resource(
        self, book_id: int, user_id: int, path: str
    ) -> PublicationResourceView:
        """Return the file the reader asked for.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no stored EPUB to read.
            InvalidEbookError: If the stored EPUB cannot be parsed.
            PublicationResourceNotFoundError: If the publication lists no such
                file.
        """
        resource = await self.publication_resource_query.get_publication_resource(
            BookId(book_id), UserId(user_id), path
        )
        if resource is None:
            raise BookNotFoundError(book_id)
        return resource
