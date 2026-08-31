"""Domain service turning a book's reading sessions into the numbers a reader sees."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, tzinfo

from src.domain.common.value_objects.position import Position
from src.domain.reading.services.reading_activity_calculator import (
    ReadingActivity,
    ReadingActivityCalculator,
)
from src.domain.reading.services.reading_stretch import ReadingStretch, day_in


@dataclass(frozen=True)
class ReadingStatistics:
    """What a book's reading sessions add up to.

    Every field is ``None`` when there is nothing to compute it from, rather
    than zero: a book nobody has opened has no average session, one with no
    recorded position is not at 0% -- it is unknown -- and a book with no day
    worth colouring has no activity grid.
    """

    session_count: int
    total_reading_seconds: int
    average_session_seconds: int | None
    first_session_start: datetime | None
    last_session_end: datetime | None
    span_days: int | None
    progress_percent: int | None
    activity: ReadingActivity | None


class ReadingStatisticsCalculator:
    """Computes a book's reading statistics.

    Every rule the numbers rest on lives here: what "how far through" means,
    how a span of reading is counted, and what is simply unknown. The daily
    grid is the one part it does not decide -- ``ReadingActivityCalculator``
    owns that, and this service asks it, so a caller still assembles the whole
    of ``ReadingStatistics`` in one call.
    """

    def __init__(self, activity_calculator: ReadingActivityCalculator) -> None:
        self.activity_calculator = activity_calculator

    def calculate(
        self,
        stretches: Sequence[ReadingStretch],
        reading_position: Position | None,
        book_end_position: Position | None,
        today: date,
        zone: tzinfo,
    ) -> ReadingStatistics:
        """Aggregate a book's stretches of reading, as a reader in ``zone`` counts them.

        Progress is computed whether or not any session was recorded: a book
        can carry a reading position from before Crossbill saw it. ``today`` is
        the reader's own today, which the activity grid's window ends on.
        """
        progress_percent = self._progress_percent(reading_position, book_end_position)
        activity = self.activity_calculator.calculate(stretches, today, zone)
        if not stretches:
            return ReadingStatistics(
                session_count=0,
                total_reading_seconds=0,
                average_session_seconds=None,
                first_session_start=None,
                last_session_end=None,
                span_days=None,
                progress_percent=progress_percent,
                activity=activity,
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
            activity=activity,
        )

    def _span_days(self, first_start: datetime, last_end: datetime, zone: tzinfo) -> int:
        """The calendar days the reading spanned, counted inclusively.

        A book read in one sitting spans one day, not none: the number answers
        "over how many days", so the day the reader started on counts.
        """
        return (day_in(last_end, zone) - day_in(first_start, zone)).days + 1

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
