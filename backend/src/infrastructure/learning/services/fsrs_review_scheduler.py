"""ReviewScheduler adapter backed by the PyPI ``fsrs`` package."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from fsrs import Card, Rating, ReviewLog, Scheduler, State

from src.domain.learning.value_objects.flashcard_review import FlashcardRating, FlashcardReview
from src.domain.learning.value_objects.review_state import ReviewPhase, ReviewState

# One step each, so a card missed in the morning shows again in the evening.
LEARNING_STEPS = (timedelta(hours=8),)
RELEARNING_STEPS = (timedelta(hours=8),)
DESIRED_RETENTION = 0.9

# fsrs matches review logs to their card by id; any fixed one will do.
_CARD_ID = 0

_RATINGS = {
    FlashcardRating.AGAIN: Rating.Again,
    FlashcardRating.HARD: Rating.Hard,
    FlashcardRating.GOOD: Rating.Good,
    FlashcardRating.EASY: Rating.Easy,
}
_PHASES = {
    State.Learning: ReviewPhase.LEARNING,
    State.Review: ReviewPhase.REVIEW,
    State.Relearning: ReviewPhase.RELEARNING,
}
_STATES = {phase: state for state, phase in _PHASES.items()}


class FsrsReviewScheduler:
    """Schedules reviews with FSRS; fuzzing spreads due dates and is off only in tests."""

    def __init__(self, enable_fuzzing: bool = True) -> None:
        self._scheduler = _scheduler(enable_fuzzing)
        self._unfuzzed_scheduler = _scheduler(enable_fuzzing=False)

    def review(self, state: ReviewState | None, review: FlashcardReview) -> ReviewState:
        """The state a card in ``state`` (``None`` when new) moves to after one more review."""
        reviewed, _ = self._scheduler.review_card(
            _card(state), _RATINGS[review.rating], review_datetime=review.reviewed_at
        )
        return _review_state(reviewed)

    def preview(
        self, state: ReviewState | None, now: datetime
    ) -> Mapping[FlashcardRating, datetime]:
        """The due date each rating given at ``now`` would set, without fuzz."""
        card = _card(state)
        return {rating: self._unfuzzed_due(card, fsrs, now) for rating, fsrs in _RATINGS.items()}

    def _unfuzzed_due(self, card: Card, rating: Rating, now: datetime) -> datetime:
        reviewed, _ = self._unfuzzed_scheduler.review_card(card, rating, review_datetime=now)
        return reviewed.due

    def replay(self, reviews: Sequence[FlashcardReview]) -> ReviewState:
        """The state a new card reaches after all of ``reviews``, taken in time order."""
        logs = [
            ReviewLog(
                card_id=_CARD_ID,
                rating=_RATINGS[review.rating],
                review_datetime=review.reviewed_at,
                review_duration=None,
            )
            for review in reviews
        ]
        return _review_state(self._scheduler.reschedule_card(Card(_CARD_ID), logs))


def _scheduler(enable_fuzzing: bool) -> Scheduler:
    return Scheduler(
        desired_retention=DESIRED_RETENTION,
        learning_steps=LEARNING_STEPS,
        relearning_steps=RELEARNING_STEPS,
        enable_fuzzing=enable_fuzzing,
    )


def _card(state: ReviewState | None) -> Card:
    if state is None:
        return Card(_CARD_ID)
    return Card(
        card_id=_CARD_ID,
        state=_STATES[state.phase],
        step=state.step,
        stability=state.stability,
        difficulty=state.difficulty,
        due=state.due,
        last_review=state.last_review,
    )


def _review_state(card: Card) -> ReviewState:
    if card.stability is None or card.difficulty is None or card.last_review is None:
        raise ValueError("FSRS returned a reviewed card without its memory state")
    return ReviewState(
        phase=_PHASES[card.state],
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due,
        last_review=card.last_review,
    )
