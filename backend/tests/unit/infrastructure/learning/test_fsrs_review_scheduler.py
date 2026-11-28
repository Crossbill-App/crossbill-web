"""Tests for the FSRS adapter's rating previews."""

from datetime import UTC, datetime, timedelta

from src.domain.learning.value_objects.review_state import ReviewPhase, ReviewState
from src.infrastructure.learning.services.fsrs_review_scheduler import FsrsReviewScheduler

NOW = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def test_previews_are_unfuzzed_even_when_reviews_are_fuzzed() -> None:
    long_interval = ReviewState(
        phase=ReviewPhase.REVIEW,
        step=None,
        stability=60.0,
        difficulty=5.0,
        due=NOW,
        last_review=NOW - timedelta(days=60),
    )

    fuzzed = FsrsReviewScheduler(enable_fuzzing=True).preview(long_interval, NOW)

    assert fuzzed == FsrsReviewScheduler(enable_fuzzing=False).preview(long_interval, NOW)
