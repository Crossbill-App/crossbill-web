from collections.abc import Sequence
from typing import Protocol

from src.domain.learning.value_objects.flashcard_review import FlashcardReview
from src.domain.learning.value_objects.review_state import ReviewState


class ReviewScheduler(Protocol):
    """Port for the spaced-repetition algorithm that schedules a card from its reviews."""

    def review(self, state: ReviewState | None, review: FlashcardReview) -> ReviewState:
        """The state a card in ``state`` (``None`` when new) moves to after one more review."""
        ...

    def replay(self, reviews: Sequence[FlashcardReview]) -> ReviewState:
        """The state a new card reaches after all of ``reviews``, taken in time order."""
        ...
