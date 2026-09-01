"""Domain service laying a whole library's reading out on one activity grid.

Books are named by id alone: the titles belong to the ``library`` module's
aggregate, which the domain may not reach into.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, tzinfo

from src.domain.common.value_objects.ids import BookId
from src.domain.reading.services.reading_activity_calculator import (
    ActivityUnit,
    ActivityUnitRule,
    ReadingActivityCalculator,
)
from src.domain.reading.services.reading_stretch import ReadingStretch, day_in, moment_in


@dataclass(frozen=True)
class LibraryActivityDay:
    """One coloured square, and the books the reader spent it on."""

    day: date
    value: int
    level: int
    book_ids: tuple[BookId, ...]


@dataclass(frozen=True)
class LibraryReadingActivity:
    """Every book's reading, day by day, over the window the grid shows."""

    unit: ActivityUnit
    range_start: date
    range_end: date
    days: tuple[LibraryActivityDay, ...]


class LibraryReadingActivityCalculator:
    """Computes the daily activity grid for everything a reader has read."""

    def __init__(self, activity_calculator: ReadingActivityCalculator) -> None:
        self.activity_calculator = activity_calculator

    def calculate(
        self,
        stretches_by_book: Mapping[BookId, Sequence[ReadingStretch]],
        today: date,
        zone: tzinfo,
    ) -> LibraryReadingActivity | None:
        """Lay every book's reading on one grid, as a reader in ``zone`` counts it.

        Pages as long as any drawn session recorded them, so that one page-less
        book cannot put a whole library's year in minutes.
        """
        activity = self.activity_calculator.calculate(
            [stretch for stretches in stretches_by_book.values() for stretch in stretches],
            today,
            zone,
            ActivityUnitRule.ANY_SESSION_PAGED,
        )
        if activity is None:
            return None

        read_on = self._books_by_day(stretches_by_book, zone)
        return LibraryReadingActivity(
            unit=activity.unit,
            range_start=activity.range_start,
            range_end=activity.range_end,
            days=tuple(
                LibraryActivityDay(
                    day=day.day,
                    value=day.value,
                    level=day.level,
                    book_ids=read_on[day.day],
                )
                for day in activity.days
            ),
        )

    def _books_by_day(
        self, stretches_by_book: Mapping[BookId, Sequence[ReadingStretch]], zone: tzinfo
    ) -> dict[date, tuple[BookId, ...]]:
        # Reading order rather than most-read-first: ranking by how much of
        # each book was read would re-derive what a page or a minute is worth,
        # which is the shared calculator's rule.
        opened: dict[date, dict[BookId, datetime]] = {}
        for book_id, stretches in stretches_by_book.items():
            for stretch in stretches:
                started = moment_in(stretch.start_time, zone)
                first_sitting = opened.setdefault(day_in(stretch.start_time, zone), {})
                if book_id not in first_sitting or started < first_sitting[book_id]:
                    first_sitting[book_id] = started

        return {
            day: tuple(sorted(first_sitting, key=lambda book: (first_sitting[book], book.value)))
            for day, first_sitting in opened.items()
        }
