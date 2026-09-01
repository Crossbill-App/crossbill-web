"""Read model for the reader's whole library on one activity grid.

The grid itself is a domain value -- ``LibraryReadingActivity``, computed by
``LibraryReadingActivityCalculator`` -- which names its books by id, because
the ``reading`` module may not reach into ``library``'s aggregate. This read
model is where the two meet: the grid and its numbers, plus the titles of
the books the grid names.
See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, tzinfo
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivity,
)
from src.domain.reading.services.library_reading_stats_calculator import LibraryReadingStats


@dataclass(frozen=True)
class LibraryReadingActivityView:
    """A library's activity grid, the numbers beside it, and the titles it takes to label it.

    ``titles`` covers exactly the books the grid names, so the client can send
    each title once and reference it by id from every day it appears on.
    """

    activity: LibraryReadingActivity
    stats: LibraryReadingStats
    titles: Mapping[BookId, str]


class LibraryReadingActivityQueryProtocol(Protocol):
    """Port for reading what every book of a reader's adds up to, day by day."""

    async def get_activity(
        self, user_id: UserId, today: date, zone: tzinfo
    ) -> LibraryReadingActivityView | None:
        """Return the reader's activity grid, or ``None`` when there is none to draw.

        ``zone`` is the reader's timezone: it decides which calendar day each
        session falls on. ``today`` is that reader's own today, which the
        grid's window ends on; it is passed in rather than read from the clock
        so that what the grid covers is decided at the edge, not deep inside
        the domain.

        A reader with nothing to show is not an error: unlike a book that does
        not exist, a library nobody has read yet is a perfectly good answer.
        """
        ...
