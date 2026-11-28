"""Loading a user's flashcard for a command to change."""

from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.domain.common.value_objects.ids import FlashcardId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.exceptions import FlashcardNotFoundError


async def require_flashcard(
    flashcard_repository: FlashcardRepositoryProtocol, flashcard_id: int, user_id: int
) -> Flashcard:
    """Load a user's flashcard, raising ``FlashcardNotFoundError`` when it is absent."""
    flashcard = await flashcard_repository.find_by_id(FlashcardId(flashcard_id), UserId(user_id))
    if flashcard is None:
        raise FlashcardNotFoundError(flashcard_id)
    return flashcard
