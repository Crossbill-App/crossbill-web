"""Query adapter for a book's aggregated reading statistics.

The adapter gathers what the numbers are computed from -- the book's end
position and the timespan of every session -- and hands them to
``ReadingStatisticsCalculator``, which owns what they mean. Nothing here decides
how far through a book a position is, or how a span of days is counted.
"""

from collections.abc import Sequence
from datetime import date, tzinfo
from datetime import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.reading.services.reading_statistics_calculator import (
    ReadingStatistics,
    ReadingStatisticsCalculator,
)
from src.domain.reading.services.reading_stretch import ReadingStretch
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM

SessionRow = tuple[dt, dt, list[int] | None, int | None, int | None]
BookRow = tuple[int, list[int] | None]


def _position(raw: list[int] | None) -> Position | None:
    """Read a stored ``[index, char_index]`` pair back into a Position."""
    return Position.from_json(raw) if raw else None


class BookStatisticsQuery:
    """Serves the reading statistics from two targeted selects."""

    def __init__(
        self, db: AsyncSession, statistics_calculator: ReadingStatisticsCalculator
    ) -> None:
        self.db = db
        self.statistics_calculator = statistics_calculator

    async def get_statistics(
        self, book_id: BookId, user_id: UserId, today: date, zone: tzinfo
    ) -> ReadingStatistics | None:
        """Return the book's statistics, or ``None`` if the user has no such book."""
        book = await self._fetch_book(book_id, user_id)
        if book is None:
            return None
        _, book_end_position = book

        sessions = await self._fetch_sessions(book_id, user_id)
        stretches = [
            ReadingStretch(
                start_time=start_time,
                end_time=end_time,
                start_page=start_page,
                end_page=end_page,
            )
            for start_time, end_time, _, start_page, end_page in sessions
        ]

        reading_position = None
        if sessions:
            latest_end_position = sessions[-1][2]
            reading_position = _position(latest_end_position)

        return self.statistics_calculator.calculate(
            stretches=stretches,
            reading_position=reading_position,
            book_end_position=_position(book_end_position),
            today=today,
            zone=zone,
        )

    async def _fetch_book(self, book_id: BookId, user_id: UserId) -> BookRow | None:
        """Load the book's end position, and with it the proof that the user has the book.

        A book whose ``end_position`` is null is not a missing book: the first
        leaves progress unknown, the second is a 404.
        """
        stmt = select(BookORM.id, BookORM.end_position).where(
            BookORM.id == book_id.value,
            BookORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).tuples().first()

    async def _fetch_sessions(self, book_id: BookId, user_id: UserId) -> Sequence[SessionRow]:
        """Load every session's timespan, end position and page range, oldest first.

        A column list rather than the ORM entity: ``ReadingSession.highlights``
        is ``lazy="selectin"`` and the statistics render none of them.
        """
        stmt = (
            select(
                ReadingSessionORM.start_time,
                ReadingSessionORM.end_time,
                ReadingSessionORM.end_position,
                ReadingSessionORM.start_page,
                ReadingSessionORM.end_page,
            )
            .where(
                ReadingSessionORM.book_id == book_id.value,
                ReadingSessionORM.user_id == user_id.value,
            )
            .order_by(ReadingSessionORM.start_time)
        )
        return (await self.db.execute(stmt)).tuples().all()
