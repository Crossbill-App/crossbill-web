"""Read model for the Web Publication Manifest view.

The view DTO is ``ParsedPublication`` itself, which leaves nothing for a query
port to shape: this is the "halfway option" of
``docs/adr/0001-read-models-and-query-services.md``.
"""

import asyncio
import logging
from dataclasses import replace

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.protocols.publication_repository import (
    PublicationRepositoryProtocol,
)
from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects import BookId, UserId
from src.domain.library.entities.book import Book
from src.domain.library.exceptions import EbookFileNotFoundError
from src.domain.reading.exceptions import BookNotFoundError

logger = logging.getLogger(__name__)


class GetPublicationUseCase:
    """Serve one book's publication index, deriving it when none is stored."""

    def __init__(
        self,
        publication_repository: PublicationRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
        file_repository: FileRepositoryProtocol,
        publication_parser: PublicationParserProtocol,
    ) -> None:
        self.publication_repository = publication_repository
        self.book_repository = book_repository
        self.file_repository = file_repository
        self.publication_parser = publication_parser

    async def get_publication(self, book_id: int, user_id: int) -> ParsedPublication:
        """Return the publication the manifest renders.

        A book with no stored index -- uploaded before the index existed -- has
        one derived from its stored EPUB and kept. A publication whose package
        document states no title is titled from the book row instead.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no stored EPUB to derive from.
            InvalidEbookError: If that EPUB cannot be parsed.
        """
        publication = await self.publication_repository.get(BookId(book_id), UserId(user_id))
        if publication is not None and publication.metadata.title:
            return publication
        # One fetch answers both the ownership check on the derivation path and
        # the title fallback below.
        book = await self.book_repository.find_by_id(BookId(book_id), UserId(user_id))
        if book is None:
            raise BookNotFoundError(book_id)
        if publication is None:
            publication = await self._derive(book)
        if publication.metadata.title:
            return publication
        return replace(publication, metadata=replace(publication.metadata, title=book.title))

    async def _derive(self, book: Book) -> ParsedPublication:
        # Raises what the next guard would anyway -- `get_epub(None)` answers
        # None -- but narrows the file name to `str` for the store below.
        if book.ebook_file is None:
            raise EbookFileNotFoundError(book.id.value)
        content = await self.file_repository.get_epub(book.ebook_file)
        if content is None:
            raise EbookFileNotFoundError(book.id.value)
        # Off the event loop: parsing drives zipfile and lxml over a whole book,
        # and this is the plain GET a reader issues on open, not a slow write.
        publication = await asyncio.to_thread(self.publication_parser.parse_publication, content)
        await self._store(book.id, book.ebook_file, publication)
        return publication

    async def _store(self, book_id: BookId, file_name: str, publication: ParsedPublication) -> None:
        """Cache a derived index, letting a failed write pass.

        The caller already holds the answer, the repository has rolled the
        failure back, and the next read derives again.
        """
        try:
            await self.publication_repository.save(book_id, file_name, publication)
        except Exception:
            logger.exception("Failed to store a publication index for book %s", book_id.value)
