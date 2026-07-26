"""Use case for creating flashcards from highlights."""

import structlog

from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.domain.common.value_objects.ids import HighlightId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.reading.exceptions import HighlightNotFoundError

logger = structlog.get_logger(__name__)


class CreateFlashcardForHighlightUseCase:
    """Use case for creating flashcards from highlights."""

    def __init__(
        self,
        flashcard_repository: FlashcardRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
    ) -> None:
        """Initialize use case with repository protocols."""
        self.flashcard_repository = flashcard_repository
        self.highlight_repository = highlight_repository

    async def create_flashcard(
        self, highlight_id: int, user_id: int, question: str, answer: str
    ) -> Flashcard:
        """
        Create a new flashcard for a highlight.

        Args:
            highlight_id: ID of the highlight
            user_id: ID of the user
            question: Question text for the flashcard
            answer: Answer text for the flashcard

        Returns:
            Created flashcard domain entity

        Raises:
            NotFoundError: If highlight is not found
        """
        highlight_id_vo = HighlightId(highlight_id)
        user_id_vo = UserId(user_id)

        highlight = await self.highlight_repository.find_by_id(highlight_id_vo, user_id_vo)
        if not highlight:
            raise HighlightNotFoundError(highlight_id)

        flashcard = Flashcard.create(
            user_id=user_id_vo,
            book_id=highlight.book_id,
            question=question,
            answer=answer,
            highlight_id=highlight_id_vo,
        )
        flashcard = await self.flashcard_repository.save(flashcard)

        logger.info(
            "created_flashcard_for_highlight",
            flashcard_id=flashcard.id.value,
            highlight_id=highlight_id,
        )
        return flashcard
