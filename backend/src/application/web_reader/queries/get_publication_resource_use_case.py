"""Read model serving one file of a book's publication."""

from src.application.web_reader.queries.get_publication_use_case import GetPublicationUseCase
from src.application.web_reader.queries.publication_resource import (
    PublicationResourceQueryProtocol,
    PublicationResourceView,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.web_reader.exceptions import PublicationIndexUnavailableError


class GetPublicationResourceUseCase:
    """Serve one file of a book's publication, deriving the index when none is stored."""

    def __init__(
        self,
        publication_resource_query: PublicationResourceQueryProtocol,
        get_publication_use_case: GetPublicationUseCase,
    ) -> None:
        self.publication_resource_query = publication_resource_query
        self.get_publication_use_case = get_publication_use_case

    async def get_publication_resource(
        self, book_id: int, user_id: int, path: str
    ) -> PublicationResourceView:
        """Return the file at ``path`` inside the book's EPUB container.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no stored EPUB.
            InvalidEbookError: If the member cannot be read.
            PublicationIndexUnavailableError: If the book's index could not be stored.
            PublicationResourceNotFoundError: If the publication lists no such file.
        """
        resource = await self.publication_resource_query.get_publication_resource(
            BookId(book_id), UserId(user_id), path
        )
        if resource is not None:
            return resource
        # A book uploaded before indexes existed has no row until one is derived,
        # and deriving raises BookNotFoundError itself for a book the user does
        # not own -- so past this point the book exists.
        await self.get_publication_use_case.get_publication(book_id, user_id)
        resource = await self.publication_resource_query.get_publication_resource(
            BookId(book_id), UserId(user_id), path
        )
        if resource is None:
            raise PublicationIndexUnavailableError(book_id)
        return resource
