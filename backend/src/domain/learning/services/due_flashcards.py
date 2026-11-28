"""What makes a flashcard a Due Flashcard."""

from datetime import datetime

from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus


def is_due(flashcard: Flashcard, now: datetime) -> bool:
    """Whether the flashcard wants reviewing at ``now``: active, and never reviewed or past due."""
    if flashcard.status is not FlashcardStatus.ACTIVE:
        return False
    return flashcard.review_state is None or flashcard.review_state.due <= now
