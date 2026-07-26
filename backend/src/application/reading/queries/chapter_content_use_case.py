"""Use case for retrieving chapter text content from EPUB files."""

import structlog

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.reading.protocols.ebook_text_extraction_service import (
    EbookTextExtractionServiceProtocol,
)
from src.domain.common.exceptions import DomainError, ValidationError
from src.domain.common.value_objects.ids import ChapterId, UserId
from src.domain.reading.exceptions import BookNotFoundError, ChapterNotFoundError

logger = structlog.get_logger(__name__)


class ChapterContentUseCase:
    """Use case for extracting chapter text content from EPUB files."""

    def __init__(
        self,
        chapter_repo: ChapterRepositoryProtocol,
        book_repo: BookRepositoryProtocol,
        file_repo: FileRepositoryProtocol,
        text_extraction_service: EbookTextExtractionServiceProtocol,
    ) -> None:
        self.chapter_repo = chapter_repo
        self.book_repo = book_repo
        self.file_repo = file_repo
        self.text_extraction = text_extraction_service

    async def get_chapter_content(self, chapter_id: int, user_id: int) -> tuple[str, str, int]:
        """Extract text content for a chapter.

        Args:
            chapter_id: ID of the chapter
            user_id: ID of the authenticated user

        Returns:
            Tuple of (content, chapter_name, book_id)

        Raises:
            NotFoundError: Chapter not found
            DomainError: Chapter has no position data or EPUB not available
        """
        chapter_id_vo = ChapterId(chapter_id)
        user_id_vo = UserId(user_id)

        # 1. Verify chapter exists and user owns it
        chapter = await self.chapter_repo.find_by_id(chapter_id_vo, user_id_vo)
        if not chapter:
            raise ChapterNotFoundError(chapter_id)

        # 2. Check chapter has XPoint data
        if not chapter.start_xpoint:
            raise ValidationError(
                "Chapter does not have position data. EPUB must be uploaded with chapter positions."
            )

        # 3. Resolve epub path
        book = await self.book_repo.find_by_id(chapter.book_id, user_id_vo)
        if not book or not book.ebook_file or book.file_type != "epub":
            raise BookNotFoundError(chapter.book_id.value)

        epub_content = await self.file_repo.get_epub(book.ebook_file)
        if not epub_content:
            raise BookNotFoundError(chapter.book_id.value)

        # 4. Extract chapter text
        try:
            content = self.text_extraction.extract_chapter_text(
                epub_content=epub_content,
                start_xpoint=chapter.start_xpoint,
                end_xpoint=chapter.end_xpoint,
            )
        except Exception as e:
            logger.error("failed_to_extract_chapter_content", error=str(e))
            raise DomainError(f"Failed to extract chapter content: {e}") from e

        logger.info(
            "chapter_content_extracted",
            chapter_id=chapter_id,
            content_length=len(content),
        )

        return content, chapter.name, chapter.book_id.value
