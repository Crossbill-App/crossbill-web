"""FlashcardReview value object."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from src.domain.common.exceptions import ValidationError


class FlashcardRating(StrEnum):
    """How well the reader recalled a card, on the four-point FSRS scale."""

    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


class ReviewArrival(StrEnum):
    """Where a recorded review falls among the reviews a card already has."""

    DUPLICATE = "duplicate"
    IN_ORDER = "in_order"
    LATE = "late"


@dataclass(frozen=True)
class FlashcardReview:
    """One rating of a flashcard, at the time the reader's client says it was given."""

    rating: FlashcardRating
    reviewed_at: datetime

    def __post_init__(self) -> None:
        if self.reviewed_at.tzinfo is None:
            raise ValidationError("A review time needs a timezone", field="reviewed_at")
        object.__setattr__(self, "reviewed_at", self.reviewed_at.astimezone(UTC))
