"""What one reading session contributes to the numbers computed from it.

Its own module because both ``ReadingStatisticsCalculator`` and
``ReadingActivityCalculator`` are fed the same stretches and must bucket them
onto the same calendar days; leaving this in either service would make the two
import each other.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, tzinfo


def _as_aware(moment: datetime) -> datetime:
    """Read a zoneless timestamp as UTC -- every store we read sessions from records UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def moment_in(moment: datetime, zone: tzinfo) -> datetime:
    """A moment as the clock on the reader's wall showed it.

    Two timestamps are only comparable once both have been read this way: the
    stores we load sessions from record UTC, but not all of them say so.
    """
    return _as_aware(moment).astimezone(zone)


def day_in(moment: datetime, zone: tzinfo) -> date:
    """The calendar day a moment falls on for a reader in ``zone``."""
    return moment_in(moment, zone).date()


@dataclass(frozen=True)
class ReadingStretch:
    """What one reading session contributes: when it ran, and how far it got.

    Carries no identity, device or reading position -- only the timespan and,
    where KOReader reported them, the pages the session covered. A session sent
    as xpoints alone has neither page, which is why ``has_pages`` exists rather
    than a default of zero.
    """

    start_time: datetime
    end_time: datetime
    start_page: int | None = None
    end_page: int | None = None

    @property
    def has_pages(self) -> bool:
        """Whether this session recorded where in the book's pages it ran."""
        return self.start_page is not None and self.end_page is not None

    @property
    def pages_read(self) -> int:
        """Pages the session covered, or zero when it recorded none.

        Never negative: the write side rejects a session that ends on an
        earlier page than it starts, and a legacy row that slipped through
        should cost the reader one pale square rather than a broken scale.
        """
        if self.start_page is None or self.end_page is None:
            return 0
        return max(0, self.end_page - self.start_page)

    @property
    def duration_seconds(self) -> int:
        """How long the stretch ran.

        Never negative: the write side rejects a session that ends before it
        starts, and a legacy row that slipped through should cost the reader a
        wrong total rather than the whole page.
        """
        elapsed = (_as_aware(self.end_time) - _as_aware(self.start_time)).total_seconds()
        return max(0, round(elapsed))
