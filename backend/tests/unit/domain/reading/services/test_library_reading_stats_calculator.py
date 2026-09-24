"""Tests for the numbers shown beside the library-wide activity grid."""

from datetime import UTC, date, datetime, timedelta, tzinfo

import pytest

from src.domain.common.value_objects.ids import BookId
from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivity,
    LibraryReadingActivityCalculator,
)
from src.domain.reading.services.library_reading_stats_calculator import (
    LibraryReadingStats,
    LibraryReadingStatsCalculator,
)
from src.domain.reading.services.reading_activity_calculator import ReadingActivityCalculator
from src.domain.reading.services.reading_stretch import ReadingStretch

DUNE = BookId(1)
EMMA = BookId(2)

TODAY = date(2024, 6, 1)


@pytest.fixture
def calculator() -> LibraryReadingStatsCalculator:
    return LibraryReadingStatsCalculator()


def session(day: date, minutes: int = 30, pages: int | None = 10, hour: int = 20) -> ReadingStretch:
    """A session on ``day``; ``pages=None`` is one KOReader synced by xpoint alone."""
    start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)
    return ReadingStretch(
        start_time=start,
        end_time=start + timedelta(minutes=minutes),
        start_page=None if pages is None else 0,
        end_page=pages,
    )


def grid(
    stretches_by_book: dict[BookId, list[ReadingStretch]],
    today: date = TODAY,
    zone: tzinfo = UTC,
) -> LibraryReadingActivity:
    """The grid the stats are counted against, drawn by the service that owns it."""
    activity = LibraryReadingActivityCalculator(ReadingActivityCalculator()).calculate(
        stretches_by_book, today, zone
    )
    assert activity is not None
    return activity


def stats_for(
    calculator: LibraryReadingStatsCalculator,
    stretches_by_book: dict[BookId, list[ReadingStretch]],
    today: date = TODAY,
    zone: tzinfo = UTC,
) -> LibraryReadingStats:
    return calculator.calculate(
        stretches_by_book, grid(stretches_by_book, today, zone), today, zone
    )


def test_a_streak_runs_back_from_today(calculator: LibraryReadingStatsCalculator) -> None:
    stats = stats_for(
        calculator,
        {DUNE: [session(TODAY - timedelta(days=days)) for days in (0, 1, 2, 4)]},
    )

    assert stats.streak_days == 3


def test_a_gap_of_two_days_ends_the_streak(calculator: LibraryReadingStatsCalculator) -> None:
    stats = stats_for(
        calculator,
        {DUNE: [session(TODAY - timedelta(days=days)) for days in (2, 3, 4)]},
    )

    assert stats.streak_days == 0


def test_days_and_books_count_what_the_grid_drew(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    stats = stats_for(
        calculator,
        {
            DUNE: [session(date(2024, 5, 30)), session(date(2024, 5, 31))],
            EMMA: [session(date(2024, 5, 31), hour=9)],
        },
    )

    assert stats.days_read == 2
    assert stats.books_read == 2
