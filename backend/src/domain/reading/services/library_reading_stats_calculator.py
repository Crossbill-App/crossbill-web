"""Domain service turning a library's year of reading into the numbers beside its grid.

The grid says which days were read and how darkly. These are the same year said
in words: how long today got, how long the year did, how many days in a row the
reading has been kept up, and how much of the library it covered.

Counted over the window the grid spans, but from the reading itself rather than
from the squares. A day whose sessions got through no pages is a day the reader
read on, and it belongs in every number here -- while the grid, which colours a
day by how much of it was read, has nothing to colour that day with. Sourcing
the numbers from the drawn days instead would answer "25m" to what was read
today and "yesterday" to when the reader last read, in the same breath.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta, tzinfo

from src.domain.common.value_objects.ids import BookId
from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivity,
)
from src.domain.reading.services.reading_stretch import ReadingStretch, day_in


@dataclass(frozen=True)
class LibraryReadingStats:
    """What the year on the grid adds up to.

    Every field is a number rather than ``None``: these are only ever computed
    for a reader who has a grid, and a grid exists only once some day was worth
    colouring -- which takes a session inside the window.
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
        stretches_by_book: Mapping[BookId, Sequence[ReadingStretch]],
        activity: LibraryReadingActivity,
        today: date,
        zone: tzinfo,
    ) -> LibraryReadingStats:
        """Sum up the year ``activity`` spans, as a reader in ``zone`` counts it.

        ``stretches_by_book`` is every session the reader has, window or not;
        the ones outside are dropped here rather than by the caller, so that
        the window the numbers cover is the one the grid was drawn over.
        """
        read = self._within_window(stretches_by_book, activity, zone)
        read_on = {day_in(stretch.start_time, zone) for stretch in self._all(read)}

        return LibraryReadingStats(
            last_read_day=max(read_on),
            seconds_today=sum(
                stretch.duration_seconds
                for stretch in self._all(read)
                if day_in(stretch.start_time, zone) == today
            ),
            total_seconds=sum(stretch.duration_seconds for stretch in self._all(read)),
            streak_days=self._streak(read_on, today),
            days_read=len(read_on),
            books_read=len(read),
        )

    def _within_window(
        self,
        stretches_by_book: Mapping[BookId, Sequence[ReadingStretch]],
        activity: LibraryReadingActivity,
        zone: tzinfo,
    ) -> dict[BookId, list[ReadingStretch]]:
        """The reading the grid's window covers, by book, dropping books it leaves out."""
        within = {
            book_id: [
                stretch
                for stretch in stretches
                if activity.range_start <= day_in(stretch.start_time, zone) <= activity.range_end
            ]
            for book_id, stretches in stretches_by_book.items()
        }
        return {book_id: stretches for book_id, stretches in within.items() if stretches}

    def _all(self, read: Mapping[BookId, Sequence[ReadingStretch]]) -> list[ReadingStretch]:
        """Every session of every book, the books no longer told apart."""
        return [stretch for stretches in read.values() for stretch in stretches]

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
