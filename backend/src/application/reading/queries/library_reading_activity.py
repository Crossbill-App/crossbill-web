"""Read model for the reader's whole library on one activity grid.

The grid names its books by id, because the ``reading`` module may not reach
into ``library``'s aggregate; this is where the two meet. See
``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import date, tzinfo
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivity,
)
from src.domain.reading.services.library_reading_stats_calculator import LibraryReadingStats


@dataclass(frozen=True)
class ActivityBookView:
    """A book the grid names: the id its days reference, and what to call it."""

    id: BookId
    title: str


@dataclass(frozen=True)
class LibraryReadingActivityView:
    """A library's activity grid, the numbers beside it, and the books it names."""

    activity: LibraryReadingActivity
    stats: LibraryReadingStats
    books: tuple[ActivityBookView, ...]


class LibraryReadingActivityQueryProtocol(Protocol):
    """Port for reading what every book of a reader's adds up to, day by day."""

    async def get_activity(
        self, user_id: UserId, today: date, zone: tzinfo
    ) -> LibraryReadingActivityView | None:
        """Return the reader's activity grid, or ``None`` when there is none to draw.

        ``today`` is the reader's own, passed in rather than read from the clock
        so the window is decided at the edge. A library nobody has read yet is an
        answer, not an error.
        """
        ...
