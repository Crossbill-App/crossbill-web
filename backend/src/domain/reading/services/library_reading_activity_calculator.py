"""Domain service laying a whole library's reading out on one activity grid.

The grid itself is ``ReadingActivityCalculator``'s -- the same squares, window
and shades a single book's page draws. What this service adds is which books
each square is made of, and the looser unit rule a many-book grid needs.

Books are named by id alone. The titles a reader sees belong to the ``library``
module's aggregate, so they are resolved outside the domain, where a read model
is free to span modules.
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
    """Every book's reading, day by day, over the window the grid shows.

    Shaped like ``ReadingActivity`` and read the same way: ``days`` carries
    only the days with something to show, oldest first, and the window is
    ``range_start``..``range_end`` regardless.
    """

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

        The numbers, the window and the four shades are the shared calculator's
        answer over the reading of every book at once, so a day's square is as
        dark as that day was across the library. Only the unit rule differs:
        pages as long as any drawn session recorded them, so that one page-less
        book cannot put a whole library's year in minutes.

        Returns ``None`` whenever the shared calculator has no square to
        colour -- a reader with no sessions, none inside the window, or none
        there that nets a positive day.
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
                    # Every drawn day was drawn from some session, so the day
                    # is always one this mapping has.
                    book_ids=read_on[day.day],
                )
                for day in activity.days
            ),
        )

    def _books_by_day(
        self, stretches_by_book: Mapping[BookId, Sequence[ReadingStretch]], zone: tzinfo
    ) -> dict[date, tuple[BookId, ...]]:
        """The books read on each day, in the order the reader opened them.

        Reading order rather than most-read-first: it needs nothing but the
        times already used to bucket the days, whereas ranking by how much of
        each book was read would re-derive, out here, what a page or a minute
        is worth -- a rule the shared calculator owns.

        A book read twice in a day is named once, at the earlier sitting. A
        book whose session got through nothing is named all the same: the
        reader did read it that day, and only the day's total decides whether
        the square is drawn at all.
        """
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
