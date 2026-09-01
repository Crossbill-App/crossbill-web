"""Tests for the numbers shown beside the library-wide activity grid."""

from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

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

HELSINKI = ZoneInfo("Europe/Helsinki")

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


def test_the_last_day_read_is_the_grids_own_last_square(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    stats = stats_for(calculator, {DUNE: [session(date(2024, 3, 1)), session(date(2024, 5, 30))]})

    assert stats.last_read_day == date(2024, 5, 30)


def test_today_counts_only_what_was_read_today(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    stats = stats_for(
        calculator,
        {
            DUNE: [session(TODAY, minutes=25), session(date(2024, 5, 31), minutes=90)],
            EMMA: [session(TODAY, minutes=15, hour=9)],
        },
    )

    assert stats.seconds_today == (25 + 15) * 60


def test_a_day_with_nothing_read_yet_counts_no_seconds(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    stats = stats_for(calculator, {DUNE: [session(date(2024, 5, 31), minutes=45)]})

    assert stats.seconds_today == 0
    assert stats.total_seconds == 45 * 60


def test_reading_from_before_the_window_is_not_in_the_total(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    # The window is the 365 days ending today, so a session a year and a half
    # back is on no square and belongs in no total either.
    outside = session(date(2022, 1, 1), minutes=120)
    inside = session(date(2024, 5, 20), minutes=30)

    stats = calculator.calculate({DUNE: [outside, inside]}, grid({DUNE: [inside]}), TODAY, UTC)

    assert stats.total_seconds == 30 * 60
    assert stats.days_read == 1


def test_a_streak_runs_back_from_today(calculator: LibraryReadingStatsCalculator) -> None:
    stats = stats_for(
        calculator,
        {DUNE: [session(TODAY - timedelta(days=days)) for days in (0, 1, 2, 4)]},
    )

    assert stats.streak_days == 3


def test_a_today_not_read_yet_keeps_last_nights_streak(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    stats = stats_for(
        calculator,
        {DUNE: [session(TODAY - timedelta(days=days)) for days in (1, 2, 3)]},
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


def test_the_readers_own_midnight_decides_which_day_is_today(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    # 22:30 UTC on 31 May is half past one on 1 June in Helsinki, so a reader
    # there has read today even though UTC says they read yesterday.
    late = ReadingStretch(
        start_time=datetime(2024, 5, 31, 22, 30, tzinfo=UTC),
        end_time=datetime(2024, 5, 31, 23, 0, tzinfo=UTC),
        start_page=0,
        end_page=10,
    )

    stats = stats_for(calculator, {DUNE: [late]}, zone=HELSINKI)

    assert stats.last_read_day == TODAY
    assert stats.seconds_today == 30 * 60
    assert stats.streak_days == 1


def test_reading_the_grid_could_not_colour_still_counts(
    calculator: LibraryReadingStatsCalculator,
) -> None:
    """A page-less day is a day read, even though no square can be drawn for it."""
    stats = stats_for(
        calculator,
        {
            DUNE: [session(date(2024, 5, 30)), session(date(2024, 5, 31))],
            EMMA: [session(TODAY, minutes=25, pages=None, hour=9)],
        },
    )

    assert stats.last_read_day == TODAY
    assert stats.seconds_today == 25 * 60
    assert stats.streak_days == 3
    assert stats.days_read == 3
    assert stats.books_read == 2
