"""Tests for the reading-activity domain service."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.domain.reading.services.reading_activity_calculator import (
    ActivityUnit,
    ReadingActivityCalculator,
)
from src.domain.reading.services.reading_stretch import ReadingStretch

HELSINKI = ZoneInfo("Europe/Helsinki")

# Every fixture below is read in March 2024, so a today in June 2024 is inside
# the window for some tests and a today in 2026 is outside it for others.
RECENTLY = date(2024, 6, 1)
YEARS_LATER = date(2026, 6, 1)


@pytest.fixture
def calculator() -> ReadingActivityCalculator:
    return ReadingActivityCalculator()


def paged(day: date, pages: int, at_page: int = 0, minutes: int = 20) -> ReadingStretch:
    """A session on ``day`` that got through ``pages`` pages."""
    start = datetime(day.year, day.month, day.day, 20, 0, tzinfo=UTC)
    return ReadingStretch(
        start_time=start,
        end_time=start + timedelta(minutes=minutes),
        start_page=at_page,
        end_page=at_page + pages,
    )


def timed(start: datetime, seconds: int) -> ReadingStretch:
    """A session with no page numbers, as KOReader sends for an xpoint-only book."""
    return ReadingStretch(start_time=start, end_time=start + timedelta(seconds=seconds))


def levels_by_day(
    calculator: ReadingActivityCalculator, stretches: list[ReadingStretch]
) -> dict[date, int]:
    """The grid as ``{day: level}``, for tests that only care about the colours."""
    activity = calculator.calculate(stretches, RECENTLY, UTC)
    assert activity is not None
    return {day.day: day.level for day in activity.days}


def test_a_book_with_no_sessions_has_no_grid(calculator: ReadingActivityCalculator) -> None:
    assert calculator.calculate([], RECENTLY, UTC) is None


def test_pages_are_counted_when_every_session_recorded_them(
    calculator: ReadingActivityCalculator,
) -> None:
    activity = calculator.calculate(
        [paged(date(2024, 3, 1), pages=10), paged(date(2024, 3, 2), pages=30, at_page=10)],
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert activity.unit is ActivityUnit.PAGES
    assert [day.value for day in activity.days] == [10, 30]


def test_one_session_without_pages_puts_the_whole_book_on_minutes(
    calculator: ReadingActivityCalculator,
) -> None:
    """All-or-nothing: a mixed book must not render its page-less days blank."""
    stretches = [
        paged(date(2024, 3, 1), pages=10, minutes=30),
        timed(datetime(2024, 3, 2, 20, 0, tzinfo=UTC), seconds=45 * 60),
    ]

    activity = calculator.calculate(stretches, RECENTLY, UTC)

    assert activity is not None
    assert activity.unit is ActivityUnit.MINUTES
    assert [day.value for day in activity.days] == [30, 45]


def test_sessions_on_one_day_are_added_together(calculator: ReadingActivityCalculator) -> None:
    morning = ReadingStretch(
        start_time=datetime(2024, 3, 1, 8, 0, tzinfo=UTC),
        end_time=datetime(2024, 3, 1, 8, 30, tzinfo=UTC),
        start_page=0,
        end_page=12,
    )
    evening = ReadingStretch(
        start_time=datetime(2024, 3, 1, 20, 0, tzinfo=UTC),
        end_time=datetime(2024, 3, 1, 20, 30, tzinfo=UTC),
        start_page=12,
        end_page=20,
    )

    activity = calculator.calculate([morning, evening], RECENTLY, UTC)

    assert activity is not None
    assert [(day.day, day.value) for day in activity.days] == [(date(2024, 3, 1), 20)]


def test_a_day_is_the_readers_own_day(calculator: ReadingActivityCalculator) -> None:
    """00:15 and 07:00 on 16 March in Helsinki are 15 and 16 March in UTC."""
    stretches = [
        timed(datetime(2024, 3, 15, 22, 15, tzinfo=UTC), seconds=20 * 60),
        timed(datetime(2024, 3, 16, 5, 0, tzinfo=UTC), seconds=20 * 60),
    ]

    in_utc = calculator.calculate(stretches, RECENTLY, UTC)
    in_helsinki = calculator.calculate(stretches, RECENTLY, HELSINKI)

    assert in_utc is not None
    assert in_helsinki is not None
    assert [(day.day, day.value) for day in in_utc.days] == [
        (date(2024, 3, 15), 20),
        (date(2024, 3, 16), 20),
    ]
    assert [(day.day, day.value) for day in in_helsinki.days] == [(date(2024, 3, 16), 40)]


def test_a_session_running_past_midnight_counts_on_the_day_it_began(
    calculator: ReadingActivityCalculator,
) -> None:
    late = ReadingStretch(
        start_time=datetime(2024, 3, 1, 23, 30, tzinfo=UTC),
        end_time=datetime(2024, 3, 2, 1, 0, tzinfo=UTC),
        start_page=0,
        end_page=25,
    )

    activity = calculator.calculate([late], RECENTLY, UTC)

    assert activity is not None
    assert [day.day for day in activity.days] == [date(2024, 3, 1)]


def test_minutes_are_summed_before_they_are_rounded(
    calculator: ReadingActivityCalculator,
) -> None:
    """Two glances at the book make a minute between them, not nothing twice over."""
    stretches = [
        timed(datetime(2024, 3, 1, 8, 0, tzinfo=UTC), seconds=20),
        timed(datetime(2024, 3, 1, 9, 0, tzinfo=UTC), seconds=20),
    ]

    activity = calculator.calculate(stretches, RECENTLY, UTC)

    assert activity is not None
    assert [day.value for day in activity.days] == [1]


def test_the_shades_divide_at_multiples_of_this_books_typical_day(
    calculator: ReadingActivityCalculator,
) -> None:
    """The median of these is 17.5, so the cuts fall at 8.75, 17.5 and 26.25.

    The 400-page day is the point of the fixture. Against the mean, which is 65
    here, all six ordinary days would come out on the palest shade; against the
    median they keep the three shades that tell them apart.
    """
    pages = [3, 8, 12, 15, 20, 22, 40, 400]
    stretches = [paged(date(2024, 3, day), pages=count) for day, count in enumerate(pages, start=1)]

    levels = levels_by_day(calculator, stretches)

    assert list(levels.values()) == [1, 1, 2, 2, 3, 3, 4, 4]


def test_days_that_read_the_same_get_the_same_shade(
    calculator: ReadingActivityCalculator,
) -> None:
    pages = [20, 20, 20, 25]
    stretches = [paged(date(2024, 3, day), pages=count) for day, count in enumerate(pages, start=1)]

    levels = list(levels_by_day(calculator, stretches).values())

    assert levels[0] == levels[1] == levels[2]


def test_a_book_read_on_one_day_alone_comes_out_mid_scale(
    calculator: ReadingActivityCalculator,
) -> None:
    """Neither the darkest shade, which would overstate it, nor the palest."""
    levels = levels_by_day(calculator, [paged(date(2024, 3, 1), pages=60)])

    assert list(levels.values()) == [2]


def test_a_day_that_turned_no_pages_gets_no_square(
    calculator: ReadingActivityCalculator,
) -> None:
    """Level 0 means nothing to show, so a page-less day is simply omitted."""
    stretches = [
        paged(date(2024, 3, 1), pages=20),
        paged(date(2024, 3, 2), pages=0, at_page=20, minutes=55),
    ]

    activity = calculator.calculate(stretches, RECENTLY, UTC)

    assert activity is not None
    assert [day.day for day in activity.days] == [date(2024, 3, 1)]


def test_a_book_whose_every_day_turned_no_pages_has_no_grid(
    calculator: ReadingActivityCalculator,
) -> None:
    activity = calculator.calculate([paged(date(2024, 3, 1), pages=0)], RECENTLY, UTC)

    assert activity is None


def test_the_window_ends_today_for_a_book_read_within_the_year(
    calculator: ReadingActivityCalculator,
) -> None:
    """So an unread fortnight shows as the gap it is, rather than being cropped away."""
    activity = calculator.calculate([paged(date(2024, 3, 1), pages=20)], RECENTLY, UTC)

    assert activity is not None
    assert activity.range_end == RECENTLY
    assert activity.range_start == date(2023, 6, 3)


def test_the_window_ends_on_the_last_session_for_a_book_left_long_ago(
    calculator: ReadingActivityCalculator,
) -> None:
    """Anchoring on today would render a year of nothing."""
    activity = calculator.calculate([paged(date(2024, 3, 1), pages=20)], YEARS_LATER, UTC)

    assert activity is not None
    assert activity.range_end == date(2024, 3, 1)
    assert activity.range_start == date(2023, 3, 3)


def test_a_session_dated_in_the_future_does_not_move_the_window(
    calculator: ReadingActivityCalculator,
) -> None:
    """A device with a reset clock must not carry the grid off after it.

    Anchoring on the future day would put the window years ahead and leave
    every real reading day outside it -- the reader would lose the whole grid
    to one bad timestamp.
    """
    real = [paged(date(2024, 5, d), pages=20, at_page=d * 20) for d in range(1, 6)]
    skewed = paged(date(2027, 1, 1), pages=5, at_page=900)

    activity = calculator.calculate([*real, skewed], RECENTLY, UTC)

    assert activity is not None
    assert activity.range_end == RECENTLY
    assert [day.day for day in activity.days] == [date(2024, 5, d) for d in range(1, 6)]


def test_a_book_read_only_in_the_future_has_no_grid(
    calculator: ReadingActivityCalculator,
) -> None:
    """Nothing to draw: the one session is not reading that has happened."""
    assert calculator.calculate([paged(date(2027, 1, 1), pages=20)], RECENTLY, UTC) is None


def test_the_unit_follows_the_sessions_the_grid_actually_draws(
    calculator: ReadingActivityCalculator,
) -> None:
    """A page-less session from before the window must not label this year in minutes."""
    long_ago = timed(datetime(2022, 3, 1, 20, 0, tzinfo=UTC), seconds=60 * 60)
    this_year = [paged(date(2024, 5, d), pages=20, at_page=d * 20) for d in range(1, 4)]

    activity = calculator.calculate([long_ago, *this_year], RECENTLY, UTC)

    assert activity is not None
    assert activity.unit is ActivityUnit.PAGES
    assert [day.value for day in activity.days] == [20, 20, 20]


def test_reading_older_than_the_window_is_left_off_the_grid(
    calculator: ReadingActivityCalculator,
) -> None:
    stretches = [
        paged(date(2022, 3, 1), pages=500),
        paged(date(2024, 3, 1), pages=20),
        paged(date(2024, 3, 2), pages=30, at_page=20),
    ]

    activity = calculator.calculate(stretches, RECENTLY, UTC)

    assert activity is not None
    assert [day.day for day in activity.days] == [date(2024, 3, 1), date(2024, 3, 2)]
