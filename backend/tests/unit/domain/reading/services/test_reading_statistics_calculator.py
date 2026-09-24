"""Tests for the reading-statistics domain service."""

from datetime import UTC, date, datetime, timedelta

import pytest

from src.domain.common.value_objects.position import Position
from src.domain.reading.services.reading_activity_calculator import ReadingActivityCalculator
from src.domain.reading.services.reading_statistics_calculator import (
    ReadingStatisticsCalculator,
)
from src.domain.reading.services.reading_stretch import ReadingStretch

# Well after every fixture's reading, so the activity grid these tests ignore
# never changes what the numbers they do assert on come out as.
TODAY = date(2024, 6, 1)


@pytest.fixture
def calculator() -> ReadingStatisticsCalculator:
    return ReadingStatisticsCalculator(activity_calculator=ReadingActivityCalculator())


def stretch(start: datetime, minutes: int) -> ReadingStretch:
    """A stretch of reading that ran for ``minutes`` from ``start``."""
    return ReadingStretch(start_time=start, end_time=start + timedelta(minutes=minutes))


def test_the_reading_ends_when_the_last_session_ends_not_when_the_last_one_starts(
    calculator: ReadingStatisticsCalculator,
) -> None:
    """Sessions from two devices can overlap, and the later start can end first."""
    long_one = stretch(datetime(2024, 1, 1, 20, 0, tzinfo=UTC), minutes=120)
    short_one = stretch(datetime(2024, 1, 1, 21, 0, tzinfo=UTC), minutes=10)

    statistics = calculator.calculate([long_one, short_one], None, None, TODAY, UTC)

    assert statistics.first_session_start == datetime(2024, 1, 1, 20, 0, tzinfo=UTC)
    assert statistics.last_session_end == datetime(2024, 1, 1, 22, 0, tzinfo=UTC)


def test_a_session_ending_before_it_started_contributes_no_time(
    calculator: ReadingStatisticsCalculator,
) -> None:
    """The write side rejects these; a legacy row must not turn the total negative."""
    backwards = ReadingStretch(
        start_time=datetime(2024, 1, 1, 21, 0, tzinfo=UTC),
        end_time=datetime(2024, 1, 1, 20, 0, tzinfo=UTC),
    )

    statistics = calculator.calculate(
        [stretch(datetime(2024, 1, 1, 8, 0, tzinfo=UTC), minutes=20), backwards],
        None,
        None,
        TODAY,
        UTC,
    )

    assert statistics.total_reading_seconds == 20 * 60


@pytest.mark.parametrize(
    ("reading_index", "end_index", "expected"),
    [
        (0, 200, 0),
        (50, 200, 25),
        (199, 200, 100),  # 99.5% rounds up to a book all but finished
        (250, 200, 100),  # past the end is still finished, never 125%
    ],
)
def test_progress_is_the_share_of_the_book_in_document_order(
    calculator: ReadingStatisticsCalculator, reading_index: int, end_index: int, expected: int
) -> None:
    statistics = calculator.calculate(
        [], Position(index=reading_index), Position(index=end_index), TODAY, UTC
    )

    assert statistics.progress_percent == expected


@pytest.mark.parametrize(
    ("reading_position", "book_end_position"),
    [
        (None, Position(index=200)),
        (Position(index=50), None),
        (Position(index=50), Position(index=0)),
    ],
)
def test_progress_is_unknown_without_both_ends_of_the_measurement(
    calculator: ReadingStatisticsCalculator,
    reading_position: Position | None,
    book_end_position: Position | None,
) -> None:
    statistics = calculator.calculate([], reading_position, book_end_position, TODAY, UTC)

    assert statistics.progress_percent is None
