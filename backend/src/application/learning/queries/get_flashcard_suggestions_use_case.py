"""Use case for AI-generated flashcard suggestions."""

import structlog

from src.application.ai.ai_usage_context import AIUsageContext
from src.application.learning.protocols.ai_flashcard_service import (
    AIFlashcardServiceProtocol,
)
from src.application.learning.queries.flashcard_suggestions import FlashcardSuggestion
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.domain.common.value_objects.ids import HighlightId, UserId
from src.domain.reading.exceptions import HighlightNotFoundError

logger = structlog.get_logger(__name__)


class GetFlashcardSuggestionsUseCase:
    """Use case for AI-generated flashcard suggestions."""

    def __init__(
        self,
        highlight_repository: HighlightRepositoryProtocol,
        ai_flashcard_service: AIFlashcardServiceProtocol,
    ) -> None:
        """Initialize use case with repository protocols."""
        self.highlight_repository = highlight_repository
        self.ai_flashcard_service = ai_flashcard_service

    async def get_suggestions(self, highlight_id: int, user_id: int) -> list[FlashcardSuggestion]:
        """
        Get AI-generated flashcard suggestions for a highlight.

        Args:
            highlight_id: ID of the highlight
            user_id: ID of the user (for ownership verification)

        Returns:
            List of flashcard suggestions

        Raises:
            NotFoundError: If highlight not found or user doesn't own it
        """
        highlight_id_vo = HighlightId(highlight_id)
        user_id_vo = UserId(user_id)

        highlight = await self.highlight_repository.find_by_id(highlight_id_vo, user_id_vo)
        if not highlight:
            raise HighlightNotFoundError(highlight_id)

        usage_context = AIUsageContext(
            user_id=user_id_vo,
            task_type="flashcard_suggestions",
            entity_type="highlight",
            entity_id=highlight_id,
        )
        ai_suggestions = await self.ai_flashcard_service.generate_flashcard_suggestions(
            highlight.text, usage_context
        )

        suggestions = [
            FlashcardSuggestion(question=s.question, answer=s.answer) for s in ai_suggestions
        ]

        logger.info(
            "flashcard_suggestions_generated",
            highlight_id=highlight_id,
            suggestion_count=len(suggestions),
        )

        return suggestions
