"""Tests for the library-wide reading-activity domain service."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.domain.common.value_objects.ids import BookId
from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivity,
    LibraryReadingActivityCalculator,
)
from src.domain.reading.services.reading_activity_calculator import (
    ActivityUnit,
    ReadingActivityCalculator,
)
from src.domain.reading.services.reading_stretch import ReadingStretch

HELSINKI = ZoneInfo("Europe/Helsinki")

DUNE = BookId(1)
EMMA = BookId(2)

# Every fixture below is read in March 2024, which a today in June 2024 keeps
# inside the window.
RECENTLY = date(2024, 6, 1)


@pytest.fixture
def calculator() -> LibraryReadingActivityCalculator:
    return LibraryReadingActivityCalculator(ReadingActivityCalculator())


def paged(day: date, pages: int, at_page: int = 0, hour: int = 20) -> ReadingStretch:
    """A session on ``day`` that got through ``pages`` pages."""
    start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)
    return ReadingStretch(
        start_time=start,
        end_time=start + timedelta(minutes=20),
        start_page=at_page,
        end_page=at_page + pages,
    )


def timed(start: datetime, minutes: int = 30) -> ReadingStretch:
    """A session with no page numbers, as KOReader sends for an xpoint-only book."""
    return ReadingStretch(start_time=start, end_time=start + timedelta(minutes=minutes))


def books_by_day(activity: LibraryReadingActivity) -> dict[date, tuple[BookId, ...]]:
    return {day.day: day.book_ids for day in activity.days}


def test_a_reader_with_no_sessions_has_no_grid(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    assert calculator.calculate({}, RECENTLY, UTC) is None
    assert calculator.calculate({DUNE: []}, RECENTLY, UTC) is None


def test_a_day_counts_every_book_read_on_it(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    """One square, one number: what the reader got through that day, across the library."""
    activity = calculator.calculate(
        {
            DUNE: [paged(date(2024, 3, 1), pages=10, hour=8)],
            EMMA: [paged(date(2024, 3, 1), pages=30, hour=20)],
        },
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert [(day.day, day.value) for day in activity.days] == [(date(2024, 3, 1), 40)]
    assert activity.days[0].book_ids == (DUNE, EMMA)


def test_a_days_books_are_listed_in_the_order_they_were_opened(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    activity = calculator.calculate(
        {
            DUNE: [paged(date(2024, 3, 1), pages=10, hour=21)],
            EMMA: [paged(date(2024, 3, 1), pages=30, hour=7)],
        },
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert activity.days[0].book_ids == (EMMA, DUNE)


def test_a_book_read_twice_in_a_day_is_named_once(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    activity = calculator.calculate(
        {
            DUNE: [
                paged(date(2024, 3, 1), pages=10, hour=8),
                paged(date(2024, 3, 1), pages=15, at_page=10, hour=22),
            ]
        },
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert [(day.value, day.book_ids) for day in activity.days] == [(25, (DUNE,))]


def test_one_book_without_pages_does_not_put_the_library_on_minutes(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    """The page-less book costs its own days, not every other book's unit."""
    activity = calculator.calculate(
        {
            DUNE: [
                paged(date(2024, 3, 1), pages=10),
                paged(date(2024, 3, 2), pages=30, at_page=10),
            ],
            EMMA: [timed(datetime(2024, 3, 3, 20, 0, tzinfo=UTC))],
        },
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert activity.unit is ActivityUnit.PAGES
    assert [day.day for day in activity.days] == [date(2024, 3, 1), date(2024, 3, 2)]


def test_a_book_that_got_through_nothing_is_still_named_on_a_day_that_did(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    """The reader read it; only the day's total decides whether the square is drawn."""
    activity = calculator.calculate(
        {
            DUNE: [paged(date(2024, 3, 1), pages=10, hour=20)],
            EMMA: [timed(datetime(2024, 3, 1, 8, 0, tzinfo=UTC))],
        },
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert [(day.value, day.book_ids) for day in activity.days] == [(10, (EMMA, DUNE))]


def test_the_books_of_a_day_follow_the_readers_own_midnight(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    """22:15 UTC is the next morning in Helsinki, so the two books share a day there."""
    late_on_the_fifteenth = datetime(2024, 3, 15, 22, 15, tzinfo=UTC)
    on_the_sixteenth = datetime(2024, 3, 16, 5, 0, tzinfo=UTC)
    reading = {
        DUNE: [
            ReadingStretch(
                start_time=late_on_the_fifteenth,
                end_time=late_on_the_fifteenth + timedelta(minutes=20),
                start_page=0,
                end_page=10,
            )
        ],
        EMMA: [
            ReadingStretch(
                start_time=on_the_sixteenth,
                end_time=on_the_sixteenth + timedelta(minutes=20),
                start_page=0,
                end_page=20,
            )
        ],
    }

    in_utc = calculator.calculate(reading, RECENTLY, UTC)
    in_helsinki = calculator.calculate(reading, RECENTLY, HELSINKI)

    assert in_utc is not None and in_helsinki is not None
    assert books_by_day(in_utc) == {date(2024, 3, 15): (DUNE,), date(2024, 3, 16): (EMMA,)}
    assert books_by_day(in_helsinki) == {date(2024, 3, 16): (DUNE, EMMA)}


def test_a_book_read_only_outside_the_window_names_no_day(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    activity = calculator.calculate(
        {
            DUNE: [
                paged(date(2024, 3, 1), pages=10),
                paged(date(2024, 3, 2), pages=30, at_page=10),
            ],
            EMMA: [paged(date(2022, 3, 1), pages=500)],
        },
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert books_by_day(activity) == {date(2024, 3, 1): (DUNE,), date(2024, 3, 2): (DUNE,)}


def test_the_shades_divide_at_the_librarys_typical_day(
    calculator: LibraryReadingActivityCalculator,
) -> None:
    """10, 30 and 60 pages across two books: a median of 30, so cuts at 15 and 45."""
    activity = calculator.calculate(
        {
            DUNE: [
                paged(date(2024, 3, 1), pages=10),
                paged(date(2024, 3, 3), pages=60, at_page=10),
            ],
            EMMA: [paged(date(2024, 3, 2), pages=30)],
        },
        RECENTLY,
        UTC,
    )

    assert activity is not None
    assert [day.level for day in activity.days] == [1, 2, 4]
