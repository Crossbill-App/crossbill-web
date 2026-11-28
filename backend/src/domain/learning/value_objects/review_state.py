"""ReviewState value object."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewPhase(StrEnum):
    """The FSRS state a reviewed card is in."""

    LEARNING = "learning"
    REVIEW = "review"
    RELEARNING = "relearning"


@dataclass(frozen=True)
class ReviewState:
    """The schedule a card's reviews add up to; a card with no reviews has none."""

    phase: ReviewPhase
    step: int | None
    stability: float
    difficulty: float
    due: datetime
    last_review: datetime
