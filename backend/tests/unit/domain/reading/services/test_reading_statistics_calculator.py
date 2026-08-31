"""Tests for the reading-statistics domain service."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.domain.common.value_objects.position import Position
from src.domain.reading.services.reading_statistics_calculator import (
    ReadingStatisticsCalculator,
    ReadingStretch,
)

HELSINKI = ZoneInfo("Europe/Helsinki")


@pytest.fixture
def calculator() -> ReadingStatisticsCalculator:
    return ReadingStatisticsCalculator()


def stretch(start: datetime, minutes: int) -> ReadingStretch:
    """A stretch of reading that ran for ``minutes`` from ``start``."""
    return ReadingStretch(start_time=start, end_time=start + timedelta(minutes=minutes))


def test_a_book_with_no_sessions_reports_nothing_rather_than_zero(
    calculator: ReadingStatisticsCalculator,
) -> None:
    statistics = calculator.calculate([], None, Position(index=100), UTC)

    assert statistics.session_count == 0
    assert statistics.total_reading_seconds == 0
    assert statistics.average_session_seconds is None
    assert statistics.first_session_start is None
    assert statistics.last_session_end is None
    assert statistics.span_days is None


def test_sessions_are_totalled_and_averaged(calculator: ReadingStatisticsCalculator) -> None:
    stretches = [
        stretch(datetime(2024, 1, 1, 20, 0, tzinfo=UTC), minutes=30),
        stretch(datetime(2024, 1, 2, 20, 0, tzinfo=UTC), minutes=45),
        stretch(datetime(2024, 1, 3, 20, 0, tzinfo=UTC), minutes=15),
    ]

    statistics = calculator.calculate(stretches, None, None, UTC)

    assert statistics.session_count == 3
    assert statistics.total_reading_seconds == 90 * 60
    assert statistics.average_session_seconds == 30 * 60


def test_the_reading_ends_when_the_last_session_ends_not_when_the_last_one_starts(
    calculator: ReadingStatisticsCalculator,
) -> None:
    """Sessions from two devices can overlap, and the later start can end first."""
    long_one = stretch(datetime(2024, 1, 1, 20, 0, tzinfo=UTC), minutes=120)
    short_one = stretch(datetime(2024, 1, 1, 21, 0, tzinfo=UTC), minutes=10)

    statistics = calculator.calculate([long_one, short_one], None, None, UTC)

    assert statistics.first_session_start == datetime(2024, 1, 1, 20, 0, tzinfo=UTC)
    assert statistics.last_session_end == datetime(2024, 1, 1, 22, 0, tzinfo=UTC)


def test_a_book_read_in_one_sitting_spans_a_single_day(
    calculator: ReadingStatisticsCalculator,
) -> None:
    statistics = calculator.calculate(
        [stretch(datetime(2024, 1, 1, 20, 0, tzinfo=UTC), minutes=30)], None, None, UTC
    )

    assert statistics.span_days == 1


def test_the_span_is_counted_in_the_readers_own_timezone(
    calculator: ReadingStatisticsCalculator,
) -> None:
    """Reading just past midnight and again that morning is one day to the reader."""
    stretches = [
        # 00:15 and 07:00 on 16 January in Helsinki -- 15 and 16 January in UTC.
        stretch(datetime(2024, 1, 15, 22, 15, tzinfo=UTC), minutes=30),
        stretch(datetime(2024, 1, 16, 5, 0, tzinfo=UTC), minutes=30),
    ]

    assert calculator.calculate(stretches, None, None, UTC).span_days == 2
    assert calculator.calculate(stretches, None, None, HELSINKI).span_days == 1


def test_a_zoneless_timestamp_is_read_as_utc(calculator: ReadingStatisticsCalculator) -> None:
    naive = stretch(datetime(2024, 1, 15, 23, 30, tzinfo=UTC).replace(tzinfo=None), minutes=60)

    statistics = calculator.calculate([naive], None, None, HELSINKI)

    assert statistics.total_reading_seconds == 60 * 60
    # 23:30 UTC is 01:30 the next morning in Helsinki, so the reading spans one
    # Helsinki day rather than the two it would if the zone were ignored.
    assert statistics.span_days == 1


def test_a_session_ending_before_it_started_contributes_no_time(
    calculator: ReadingStatisticsCalculator,
) -> None:
    """The write side rejects these; a legacy row must not turn the total negative."""
    backwards = ReadingStretch(
        start_time=datetime(2024, 1, 1, 21, 0, tzinfo=UTC),
        end_time=datetime(2024, 1, 1, 20, 0, tzinfo=UTC),
    )

    statistics = calculator.calculate(
        [stretch(datetime(2024, 1, 1, 8, 0, tzinfo=UTC), minutes=20), backwards], None, None, UTC
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
        [], Position(index=reading_index), Position(index=end_index), UTC
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
    statistics = calculator.calculate([], reading_position, book_end_position, UTC)

    assert statistics.progress_percent is None
