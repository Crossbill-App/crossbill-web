"""Use case for updating flashcards."""

import structlog

from src.application.common.ownership import require_flashcard
from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects.ids import FlashcardId, UserId
from src.domain.learning.entities.flashcard import Flashcard

logger = structlog.get_logger(__name__)


class UpdateFlashcardUseCase:
    """Use case for updating flashcards."""

    def __init__(
        self,
        flashcard_repository: FlashcardRepositoryProtocol,
    ) -> None:
        """Initialize use case with repository protocols."""
        self.flashcard_repository = flashcard_repository

    async def update_flashcard(
        self,
        flashcard_id: int,
        user_id: int,
        question: str | None = None,
        answer: str | None = None,
    ) -> Flashcard:
        """
        Update a flashcard's question and/or answer.

        Args:
            flashcard_id: ID of the flashcard to update
            user_id: ID of the user
            question: New question text (optional)
            answer: New answer text (optional)

        Returns:
            Updated flashcard domain entity

        Raises:
            FlashcardNotFoundError: If flashcard is not found
            ValidationError: If neither question nor answer is provided
        """
        if question is None and answer is None:
            raise ValidationError("At least one of question or answer must be provided")

        flashcard = await require_flashcard(
            self.flashcard_repository, FlashcardId(flashcard_id), UserId(user_id)
        )

        if question is not None:
            flashcard.update_question(question)
        if answer is not None:
            flashcard.update_answer(answer)

        flashcard = await self.flashcard_repository.save(flashcard)

        logger.info("updated_flashcard", flashcard_id=flashcard_id)
        return flashcard
