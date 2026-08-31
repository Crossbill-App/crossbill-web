"""Domain service turning a book's reading sessions into the numbers a reader sees."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, tzinfo

from src.domain.common.value_objects.position import Position


def _as_aware(moment: datetime) -> datetime:
    """Read a zoneless timestamp as UTC -- every store we read sessions from records UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _day_in(moment: datetime, zone: tzinfo) -> date:
    """The calendar day a moment falls on for a reader in ``zone``."""
    return _as_aware(moment).astimezone(zone).date()


@dataclass(frozen=True)
class ReadingStretch:
    """The timespan of one reading session: when it began and when it ended.

    The statistics rest on timespans alone, so this carries no identity, device
    or position -- it is what a session contributes to the numbers, not the
    session itself.
    """

    start_time: datetime
    end_time: datetime

    @property
    def duration_seconds(self) -> int:
        """How long the stretch ran.

        Never negative: the write side rejects a session that ends before it
        starts, and a legacy row that slipped through should cost the reader a
        wrong total rather than the whole page.
        """
        elapsed = (_as_aware(self.end_time) - _as_aware(self.start_time)).total_seconds()
        return max(0, round(elapsed))


@dataclass(frozen=True)
class ReadingStatistics:
    """What a book's reading sessions add up to.

    Every field is ``None`` when there is nothing to compute it from, rather
    than zero: a book nobody has opened has no average session, and one with no
    recorded position is not at 0% -- it is unknown.
    """

    session_count: int
    total_reading_seconds: int
    average_session_seconds: int | None
    first_session_start: datetime | None
    last_session_end: datetime | None
    span_days: int | None
    progress_percent: int | None


class ReadingStatisticsCalculator:
    """Computes a book's reading statistics.

    Every rule the numbers rest on lives here: what "how far through" means,
    how a span of reading is counted, and what is simply unknown.
    """

    def calculate(
        self,
        stretches: Sequence[ReadingStretch],
        reading_position: Position | None,
        book_end_position: Position | None,
        zone: tzinfo,
    ) -> ReadingStatistics:
        """Aggregate a book's stretches of reading, as a reader in ``zone`` counts them.

        Progress is computed whether or not any session was recorded: a book
        can carry a reading position from before Crossbill saw it.
        """
        progress_percent = self._progress_percent(reading_position, book_end_position)
        if not stretches:
            return ReadingStatistics(
                session_count=0,
                total_reading_seconds=0,
                average_session_seconds=None,
                first_session_start=None,
                last_session_end=None,
                span_days=None,
                progress_percent=progress_percent,
            )

        total_seconds = sum(stretch.duration_seconds for stretch in stretches)
        first_start = min(stretch.start_time for stretch in stretches)
        # The stretch that ended last, which overlapping sessions can make a
        # different one from the stretch that started last.
        last_end = max(stretch.end_time for stretch in stretches)

        return ReadingStatistics(
            session_count=len(stretches),
            total_reading_seconds=total_seconds,
            average_session_seconds=round(total_seconds / len(stretches)),
            first_session_start=first_start,
            last_session_end=last_end,
            span_days=self._span_days(first_start, last_end, zone),
            progress_percent=progress_percent,
        )

    def _span_days(self, first_start: datetime, last_end: datetime, zone: tzinfo) -> int:
        """The calendar days the reading spanned, counted inclusively.

        A book read in one sitting spans one day, not none: the number answers
        "over how many days", so the day the reader started on counts.
        """
        return (_day_in(last_end, zone) - _day_in(first_start, zone)).days + 1

    def _progress_percent(
        self, reading_position: Position | None, book_end_position: Position | None
    ) -> int | None:
        """How far through the book the reader has got, or ``None`` when unknowable.

        Measured on document order alone -- the element index, not the
        character offset within it -- and capped at 100: a reader who reached
        the book's last element has finished it, whatever the arithmetic says.
        """
        if reading_position is None or book_end_position is None or book_end_position.index <= 0:
            return None
        return min(100, round(reading_position.index / book_end_position.index * 100))
