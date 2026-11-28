from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol

from src.domain.learning.value_objects.flashcard_review import FlashcardRating, FlashcardReview
from src.domain.learning.value_objects.review_state import ReviewState


class ReviewScheduler(Protocol):
    """Port for the spaced-repetition algorithm that schedules a card from its reviews."""

    def review(self, state: ReviewState | None, review: FlashcardReview) -> ReviewState:
        """The state a card in ``state`` (``None`` when new) moves to after one more review."""
        ...

    def replay(self, reviews: Sequence[FlashcardReview]) -> ReviewState:
        """The state a new card reaches after all of ``reviews``, taken in time order."""
        ...

    def preview(
        self, state: ReviewState | None, now: datetime
    ) -> Mapping[FlashcardRating, datetime]:
        """The due date each rating given at ``now`` would set, without fuzz."""
        ...
