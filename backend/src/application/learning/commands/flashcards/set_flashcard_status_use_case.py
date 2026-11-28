"""Use case for suspending or unsuspending a flashcard."""

import structlog

from src.application.learning.flashcard_ownership import require_flashcard
from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus

logger = structlog.get_logger(__name__)


class SetFlashcardStatusUseCase:
    """Take a flashcard out of review, or put it back with its schedule intact."""

    def __init__(self, flashcard_repository: FlashcardRepositoryProtocol) -> None:
        self.flashcard_repository = flashcard_repository

    async def set_status(
        self, flashcard_id: int, user_id: int, status: FlashcardStatus
    ) -> Flashcard:
        """Give the flashcard the status.

        Raises:
            FlashcardNotFoundError: If the user has no such flashcard.
        """
        flashcard = await require_flashcard(self.flashcard_repository, flashcard_id, user_id)
        flashcard.set_status(status)
        flashcard = await self.flashcard_repository.save(flashcard)
        logger.info("set_flashcard_status", flashcard_id=flashcard_id, status=status.value)
        return flashcard
