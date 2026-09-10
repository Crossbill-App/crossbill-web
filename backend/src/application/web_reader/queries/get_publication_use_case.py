"""Read model for the Web Publication Manifest view.

The view DTO is ``ParsedPublication`` itself, which leaves nothing for a query
port to shape: this is the "halfway option" of
``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import replace

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.web_reader.protocols.publication_repository import (
    PublicationRepositoryProtocol,
)
from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetPublicationUseCase:
    """Serve one book's stored publication index to the web reader."""

    def __init__(
        self,
        publication_repository: PublicationRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.publication_repository = publication_repository
        self.book_repository = book_repository

    async def get_publication(self, book_id: int, user_id: int) -> ParsedPublication:
        """Return the publication the manifest renders.

        A publication whose package document states no title -- invalid EPUB,
        but it happens -- is titled from the book row instead, which costs the
        extra query only for those.

        Raises:
            BookNotFoundError: If the user has no such book, or none is stored.
        """
        publication = await self.publication_repository.get(BookId(book_id), UserId(user_id))
        if publication is None:
            raise BookNotFoundError(book_id)
        if publication.metadata.title:
            return publication
        book = await self.book_repository.find_by_id(BookId(book_id), UserId(user_id))
        if book is None:
            raise BookNotFoundError(book_id)
        return replace(publication, metadata=replace(publication.metadata, title=book.title))
