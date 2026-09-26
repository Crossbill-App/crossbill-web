"""Use case for creating a book from an uploaded EPUB."""

import asyncio

import structlog

from src.application.library.commands.book_files.attach_epub_use_case import AttachEpubUseCase
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.epub_parser import EpubParserProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.domain.common.value_objects.ids import UserId
from src.domain.library.entities.book import Book
from src.domain.library.entities.epub_metadata import EpubMetadata
from src.domain.library.exceptions import BookAlreadyExistsError, InvalidEbookError
from src.domain.library.services.book_identity import book_title_for, koreader_client_book_id

# The width of the books.language column.
_MAX_LANGUAGE_LENGTH = 10

logger = structlog.get_logger(__name__)


class CreateBookFromEpubUseCase:
    """Create a book from an uploaded EPUB, under the id the KOReader plugin gives it."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        epub_parser: EpubParserProtocol,
        file_repository: FileRepositoryProtocol,
        attach_epub_use_case: AttachEpubUseCase,
    ) -> None:
        self.book_repository = book_repository
        self.epub_parser = epub_parser
        self.file_repository = file_repository
        self.attach_epub_use_case = attach_epub_use_case

    async def create_book_from_epub(
        self,
        content: bytes,
        file_name: str | None,
        user_id: UserId,
        *,
        client_book_id: str | None = None,
        page_count: int | None = None,
    ) -> Book:
        """Store the EPUB on its book, creating the book unless one is waiting for a file."""
        metadata = await asyncio.to_thread(self._read_metadata, content)
        title = book_title_for(metadata.title, file_name)
        client_book_id = self._resolve_client_book_id(
            client_book_id, koreader_client_book_id(title, metadata.authors)
        )

        existing = await self.book_repository.find_by_client_book_id(client_book_id, user_id)
        if existing is not None:
            if existing.ebook_file is not None:
                raise BookAlreadyExistsError(client_book_id)
            return await self._attach_to_existing(existing, content, user_id)

        language = metadata.language
        book = Book.create(
            user_id=user_id,
            title=title,
            client_book_id=client_book_id,
            author="\n".join(metadata.authors) or None,
            language=language if language and len(language) <= _MAX_LANGUAGE_LENGTH else None,
            page_count=page_count,
        )
        book = await self.book_repository.save(book)
        try:
            return await self.attach_epub_use_case.attach_epub(book, content, user_id)
        except Exception:
            # Saves commit at once, with no unit of work: this is compensation, not rollback.
            # Row first, so a failed delete leaves a whole book, not a row naming a lost file.
            await self.book_repository.delete(book)
            await self._delete_files(book.ebook_file, book.cover_file)
            raise

    @staticmethod
    def _resolve_client_book_id(device_id: str | None, file_id: str) -> str:
        if device_id is None:
            return file_id
        if device_id != file_id:
            logger.warning(
                "client_book_id_mismatch",
                device_client_book_id=device_id,
                file_client_book_id=file_id,
            )
        return device_id

    async def _attach_to_existing(self, book: Book, content: bytes, user_id: UserId) -> Book:
        had_cover = book.cover_file is not None
        try:
            return await self.attach_epub_use_case.attach_epub(book, content, user_id)
        except Exception:
            ebook_file = book.ebook_file
            cover_file = None if had_cover else book.cover_file
            book.detach_file()
            if not had_cover:
                book.clear_cover()
            await self.book_repository.save(book)
            await self._delete_files(ebook_file, cover_file)
            raise

    async def _delete_files(self, ebook_file: str | None, cover_file: str | None) -> None:
        await self.file_repository.delete_epub(ebook_file)
        await self.file_repository.delete_cover(cover_file)

    def _read_metadata(self, content: bytes) -> EpubMetadata:
        if not self.epub_parser.validate_epub(content):
            raise InvalidEbookError("EPUB structure validation failed", ebook_type="EPUB")
        return self.epub_parser.extract_metadata(content)
