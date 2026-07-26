"""Use case for AI-generated flashcard suggestions from chapter prereading."""

import structlog

from src.application.ai.ai_usage_context import AIUsageContext
from src.application.learning.protocols.ai_flashcard_service import (
    AIFlashcardServiceProtocol,
)
from src.application.learning.queries.flashcard_suggestions import FlashcardSuggestion
from src.application.reading.protocols.chapter_prereading_repository import (
    ChapterPrereadingRepositoryProtocol,
)
from src.domain.common.value_objects.ids import ChapterId, UserId
from src.domain.reading.exceptions import ChapterPrereadingNotFoundError

logger = structlog.get_logger(__name__)


class GetChapterFlashcardSuggestionsUseCase:
    """Use case for AI-generated flashcard suggestions from chapter prereading."""

    def __init__(
        self,
        chapter_prereading_repository: ChapterPrereadingRepositoryProtocol,
        ai_flashcard_service: AIFlashcardServiceProtocol,
    ) -> None:
        self.chapter_prereading_repository = chapter_prereading_repository
        self.ai_flashcard_service = ai_flashcard_service

    async def get_suggestions(self, chapter_id: int, user_id: int) -> list[FlashcardSuggestion]:
        """
        Get AI-generated flashcard suggestions from chapter prereading content.

        Args:
            chapter_id: ID of the chapter

        Returns:
            List of flashcard suggestions

        Raises:
            NotFoundError: If chapter prereading not found
        """
        chapter_id_vo = ChapterId(chapter_id)

        prereading = await self.chapter_prereading_repository.find_by_chapter_id(chapter_id_vo)
        if not prereading:
            raise ChapterPrereadingNotFoundError(chapter_id)

        # Combine summary and keypoints into a single text block
        content_parts = [prereading.summary]
        if prereading.keypoints:
            content_parts.append("\nKey Points:")
            content_parts.extend(f"- {kp}" for kp in prereading.keypoints)
        content = "\n".join(content_parts)

        usage_context = AIUsageContext(
            user_id=UserId(user_id),
            task_type="flashcard_suggestions",
            entity_type="chapter",
            entity_id=chapter_id,
        )
        ai_suggestions = await self.ai_flashcard_service.generate_flashcard_suggestions(
            content, usage_context
        )

        suggestions = [
            FlashcardSuggestion(question=s.question, answer=s.answer) for s in ai_suggestions
        ]

        logger.info(
            "chapter_flashcard_suggestions_generated",
            chapter_id=chapter_id,
            suggestion_count=len(suggestions),
        )

        return suggestions
