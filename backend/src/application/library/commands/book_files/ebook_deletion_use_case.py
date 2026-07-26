"""Use case for ebook deletion operations."""

import logging

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.domain.library.entities.book import Book

logger = logging.getLogger(__name__)


class EbookDeletionUseCase:
    """Use case for deleting ebook files."""

    def __init__(self, file_repository: FileRepositoryProtocol) -> None:
        """Initialize use case with dependencies."""
        self.file_repository = file_repository

    async def delete_ebook(self, book: Book) -> bool:
        """
        Delete ebook file (EPUB or PDF) and cover from storage.

        Attempts to delete the ebook file and cover. Returns True if an ebook was deleted.

        Args:
            book: The book domain entity

        Returns:
            True if at least one ebook file was deleted, False if no files existed
        """
        epub_deleted = False
        pdf_deleted = False

        if book.file_type == "pdf":
            pdf_deleted = await self.file_repository.delete_pdf(book.ebook_file)
        else:
            epub_deleted = await self.file_repository.delete_epub(book.ebook_file)

        await self.file_repository.delete_cover(book.cover_file)

        if epub_deleted or pdf_deleted:
            logger.info(f"Deleted ebook file(s) for book {book.id.value}")
            return True

        logger.info(f"No ebook files found for book {book.id.value}")
        return False
