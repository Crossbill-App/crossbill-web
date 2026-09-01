"""Domain service turning a library's year of reading into the numbers beside its grid.

The grid says which days were read and how darkly. These are the same year said
in words: how long today got, how long the year did, how many days in a row the
reading has been kept up, and how much of the library it covered.

Counted over the grid's own window and its own drawn days, so that a number and
the picture beside it can never disagree -- a reader who counts the squares
gets the figure the page already told them.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta, tzinfo

from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivity,
)
from src.domain.reading.services.reading_stretch import ReadingStretch, day_in


@dataclass(frozen=True)
class LibraryReadingStats:
    """What the year on the grid adds up to.

    Every field is a number rather than ``None``: these are only ever computed
    for a reader who has a grid, and a grid exists only once some day was worth
    colouring.
    """

    last_read_day: date
    seconds_today: int
    total_seconds: int
    streak_days: int
    days_read: int
    books_read: int


class LibraryReadingStatsCalculator:
    """Computes the numbers shown beside a library's activity grid."""

    def calculate(
        self,
        stretches: Sequence[ReadingStretch],
        activity: LibraryReadingActivity,
        today: date,
        zone: tzinfo,
    ) -> LibraryReadingStats:
        """Sum up the year ``activity`` draws, as a reader in ``zone`` counts it.

        ``stretches`` is every session the reader has, window or not; the ones
        outside it are dropped here rather than by the caller, so that the
        window the numbers cover is the one the grid was drawn over.
        """
        read_on = {day.day for day in activity.days}
        in_window = [
            stretch
            for stretch in stretches
            if activity.range_start <= day_in(stretch.start_time, zone) <= activity.range_end
        ]

        return LibraryReadingStats(
            last_read_day=max(read_on),
            seconds_today=sum(
                stretch.duration_seconds
                for stretch in in_window
                if day_in(stretch.start_time, zone) == today
            ),
            total_seconds=sum(stretch.duration_seconds for stretch in in_window),
            streak_days=self._streak(read_on, today),
            days_read=len(read_on),
            books_read=len({book_id for day in activity.days for book_id in day.book_ids}),
        )

    def _streak(self, read_on: set[date], today: date) -> int:
        """Days read in a row, counting back from today.

        A day still going does not break a run: when today has nothing on it
        the count starts at yesterday, so a reader who has not opened a book
        this morning keeps last night's streak until the day is out.
        """
        day = today if today in read_on else today - timedelta(days=1)

        streak = 0
        while day in read_on:
            streak += 1
            day -= timedelta(days=1)
        return streak
