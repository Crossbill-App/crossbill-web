"""Use case for generating a chapter digest."""

from datetime import UTC, datetime

import structlog

from src.application.ai.ai_usage_context import AIUsageContext
from src.application.library.protocols.book_repository import (
    BookRepositoryProtocol,
)
from src.application.library.protocols.chapter_repository import (
    ChapterRepositoryProtocol,
)
from src.application.library.protocols.file_repository import (
    FileRepositoryProtocol,
)
from src.application.reading.protocols.ai_digest_service import (
    AIDigestServiceProtocol,
)
from src.application.reading.protocols.chapter_digest_repository import (
    ChapterDigestRepositoryProtocol,
)
from src.application.reading.protocols.ebook_text_extraction_service import (
    EbookTextExtractionServiceProtocol,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_enqueuer import EmbeddingEnqueuerProtocol
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import ChapterId, UserId
from src.domain.reading.entities.chapter_digest import (
    ChapterDigest,
)
from src.domain.reading.exceptions import BookNotFoundError, ChapterNotFoundError

logger = structlog.get_logger(__name__)


class GenerateChapterDigestUseCase:
    """Use case for generating a chapter digest."""

    def __init__(
        self,
        digest_repo: ChapterDigestRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        text_extraction_service: EbookTextExtractionServiceProtocol,
        book_repo: BookRepositoryProtocol,
        file_repo: FileRepositoryProtocol,
        ai_digest_service: AIDigestServiceProtocol,
        embedding_enqueuer: EmbeddingEnqueuerProtocol,
    ) -> None:
        self.digest_repo = digest_repo
        self.chapter_repo = chapter_repo
        self.text_extraction = text_extraction_service
        self.book_repo = book_repo
        self.file_repo = file_repo
        self.ai_digest_service = ai_digest_service
        self._embedding_enqueuer = embedding_enqueuer

    async def generate_digest(self, chapter_id: ChapterId, user_id: UserId) -> ChapterDigest:
        """Generate a new digest for a chapter."""
        # 1. Verify chapter exists and user owns it
        chapter = await self.chapter_repo.find_by_id(chapter_id, user_id)
        if not chapter:
            raise ChapterNotFoundError(chapter_id.value)

        # 2. Check if chapter has XPoint data
        if not chapter.start_xpoint:
            raise DomainError(
                "Chapter does not have position data. "
                "EPUB must be re-uploaded to extract chapter positions."
            )

        # 3. Resolve epub path
        book = await self.book_repo.find_by_id(chapter.book_id, user_id)
        if not book or not book.ebook_file or book.file_type != "epub":
            raise BookNotFoundError(chapter.book_id.value)

        epub_content = await self.file_repo.get_epub(book.ebook_file)
        if not epub_content:
            raise BookNotFoundError(chapter.book_id.value)

        # 4. Extract chapter text
        try:
            chapter_text = self.text_extraction.extract_chapter_text(
                epub_content=epub_content,
                start_xpoint=chapter.start_xpoint,
                end_xpoint=chapter.end_xpoint,
            )
        except Exception as e:
            logger.error("failed_to_extract_chapter_text", error=str(e))
            raise DomainError(f"Failed to extract chapter content: {e}") from e

        min_chapter_length = 50
        if not chapter_text or len(chapter_text.strip()) < min_chapter_length:
            raise DomainError("Chapter content is too short to generate a meaningful digest")

        # 5. Call AI service
        try:
            usage_context = AIUsageContext(
                user_id=user_id,
                task_type="digest",
                entity_type="chapter",
                entity_id=chapter_id.value,
            )
            ai_result = await self.ai_digest_service.generate_digest(chapter_text, usage_context)
        except Exception as e:
            logger.error("ai_service_failed", error=str(e))
            raise DomainError(f"Failed to generate digest: {e}") from e

        # 6. Create entity
        entity = ChapterDigest.create(
            chapter_id=chapter_id,
            summary=ai_result.summary,
            keypoints=ai_result.keypoints,
            questions=ai_result.questions,
            generated_at=datetime.now(UTC),
            ai_model="ai-configured-model",
        )

        # 7. Save and return
        logger.info(
            "digest_generated",
            chapter_id=chapter_id.value,
            keypoints_count=len(ai_result.keypoints),
        )
        saved = await self.digest_repo.save(entity)

        # The digest's id only exists after the save, and its text is what gets
        # embedded -- summary and keypoints, which is why answering the digest's
        # questions later does not re-enqueue.
        await self._embedding_enqueuer.enqueue_for(
            ContentType.DIGEST, saved.id.value, user_id.value
        )

        return saved
