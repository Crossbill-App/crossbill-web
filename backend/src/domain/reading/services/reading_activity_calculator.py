"""Domain service turning a book's reading sessions into a year of daily activity.

The calendar grid the reader sees is coloured by how much of the book was read
each day. Every rule that decides a square's colour lives here: what "how much"
means when a book has no page numbers, which 365 days the grid covers, and
where the four shades divide.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta, tzinfo
from enum import StrEnum
from statistics import median

from src.domain.reading.services.reading_stretch import ReadingStretch, day_in

WINDOW_DAYS = 365
"""Days the grid covers, the last one included."""

MAX_LEVEL = 4
"""Shades a day can be coloured, above the uncoloured level 0."""


class ActivityUnit(StrEnum):
    """What a day's number counts.

    A book is measured in pages when every session the grid draws recorded
    them, and in minutes otherwise -- see ``ReadingActivityCalculator._unit``.
    """

    PAGES = "pages"
    MINUTES = "minutes"


@dataclass(frozen=True)
class ActivityDay:
    """One coloured square: a day, what it counts, and how dark it is."""

    day: date
    value: int
    level: int


@dataclass(frozen=True)
class ReadingActivity:
    """A book's reading, day by day, over the window the grid shows.

    ``days`` carries only the days with something to show, oldest first. The
    window is ``range_start``..``range_end`` regardless, so the grid spans a
    full year whether the book was read on three days or three hundred.
    """

    unit: ActivityUnit
    range_start: date
    range_end: date
    days: tuple[ActivityDay, ...]


class ReadingActivityCalculator:
    """Computes the daily activity grid for one book.

    Deliberately per-book: the shades divide at multiples of *this* book's
    typical day, so a dense book nobody gets through quickly still shows its
    good days as good days.
    """

    def calculate(
        self, stretches: Sequence[ReadingStretch], today: date, zone: tzinfo
    ) -> ReadingActivity | None:
        """Lay the book's reading out over the window ending at the anchor day.

        ``today`` is the reader's own today, in ``zone`` -- passed in rather
        than read from the clock, so the window a test asserts on is the window
        it asked for.

        Returns ``None`` when there is no square to colour: a book with no
        sessions, none inside the window, or none there that nets a positive
        day.
        """
        if not stretches:
            return None

        range_end = self._anchor(stretches, today, zone)
        range_start = range_end - timedelta(days=WINDOW_DAYS - 1)

        # Narrowed before anything is measured, so that both the unit and the
        # shades are decided by the days the reader will actually see.
        drawn = [
            stretch
            for stretch in stretches
            if range_start <= day_in(stretch.start_time, zone) <= range_end
        ]
        if not drawn:
            return None

        unit = self._unit(drawn)
        active = {
            day: value for day, value in self._daily_totals(drawn, unit, zone).items() if value > 0
        }
        if not active:
            return None

        typical = median(active.values())
        days = tuple(
            ActivityDay(day=day, value=active[day], level=self._level(active[day], typical))
            for day in sorted(active)
        )
        return ReadingActivity(
            unit=unit,
            range_start=range_start,
            range_end=range_end,
            days=days,
        )

    def _unit(self, drawn: Sequence[ReadingStretch]) -> ActivityUnit:
        """Pages when every session on the grid recorded them, minutes otherwise.

        All-or-nothing on purpose. A book synced partly from a device that
        reported pages and partly from one that did not would, under any softer
        rule, render its page-less days as blank -- a grid that undercounts the
        reading is worse than one measured in a coarser unit.

        Only the sessions the grid draws get a say. Reading from before the
        window is not on it, so letting a page-less session from two years ago
        put this year in minutes would label the grid by something nobody can
        see on it.
        """
        if all(stretch.has_pages for stretch in drawn):
            return ActivityUnit.PAGES
        return ActivityUnit.MINUTES

    def _anchor(self, stretches: Sequence[ReadingStretch], today: date, zone: tzinfo) -> date:
        """The last day of the window.

        Today, unless the book was last read longer ago than the window is
        wide -- so an active book's grid ends on the reader's own today and an
        unread fortnight shows as the gap it is, while a book left two years
        ago still ends on its final reading day rather than showing a year of
        nothing.

        A session dated in the future never moves the window. A device with a
        reset clock can date one years ahead, and anchoring on it would carry
        the window off with it and leave every real reading day outside; such
        a session is simply not drawn.
        """
        last_day = max(day_in(stretch.start_time, zone) for stretch in stretches)
        return last_day if last_day < today - timedelta(days=WINDOW_DAYS - 1) else today

    def _daily_totals(
        self, stretches: Sequence[ReadingStretch], unit: ActivityUnit, zone: tzinfo
    ) -> dict[date, int]:
        """Add each session up onto the day it began.

        A session that runs past midnight counts wholly towards the day the
        reader sat down, which is the day they would say they read on.
        """
        if unit is ActivityUnit.PAGES:
            return self._totals_by_day(stretches, zone, lambda s: s.pages_read)

        seconds = self._totals_by_day(stretches, zone, lambda s: s.duration_seconds)
        return {day: round(total / 60) for day, total in seconds.items()}

    def _totals_by_day(
        self,
        stretches: Sequence[ReadingStretch],
        zone: tzinfo,
        amount: Callable[[ReadingStretch], int],
    ) -> dict[date, int]:
        """Sum ``amount`` per calendar day."""
        totals: dict[date, int] = {}
        for stretch in stretches:
            day = day_in(stretch.start_time, zone)
            totals[day] = totals.get(day, 0) + amount(stretch)
        return totals

    def _level(self, value: int, typical: float) -> int:
        """Which of the four shades a day earns, against this book's typical day.

        The yardstick is the median rather than the mean so that one all-day
        binge cannot flatten a year of ordinary reading into a single shade,
        and so that a book read on one day alone comes out mid-scale rather
        than at either extreme.
        """
        if value <= 0.5 * typical:
            return 1
        if value <= typical:
            return 2
        if value <= 1.5 * typical:
            return 3
        return MAX_LEVEL
