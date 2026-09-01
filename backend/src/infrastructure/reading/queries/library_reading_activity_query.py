"""Query adapter for the reader's whole library on one activity grid.

The adapter gathers the timespan of every session the reader has, hands them to
the two calculators -- which own the grid and the numbers beside it -- and then
looks up the titles of the books that ended up on the grid. Nothing here decides
which day a session belongs to, how dark a square is, or what a streak means.
"""

from collections.abc import Collection, Sequence
from datetime import date, tzinfo
from datetime import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.queries.library_reading_activity import (
    LibraryReadingActivityView,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivityCalculator,
)
from src.domain.reading.services.library_reading_stats_calculator import (
    LibraryReadingStatsCalculator,
)
from src.domain.reading.services.reading_stretch import ReadingStretch
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM

SessionRow = tuple[int, dt, dt, int | None, int | None]


class LibraryReadingActivityQuery:
    """Serves the library-wide activity grid from two targeted selects."""

    def __init__(
        self,
        db: AsyncSession,
        activity_calculator: LibraryReadingActivityCalculator,
        stats_calculator: LibraryReadingStatsCalculator,
    ) -> None:
        self.db = db
        self.activity_calculator = activity_calculator
        self.stats_calculator = stats_calculator

    async def get_activity(
        self, user_id: UserId, today: date, zone: tzinfo
    ) -> LibraryReadingActivityView | None:
        """Return the reader's activity grid, or ``None`` when there is none to draw."""
        stretches_by_book: dict[BookId, list[ReadingStretch]] = {}
        for book_id, start_time, end_time, start_page, end_page in await self._fetch_sessions(
            user_id
        ):
            stretches_by_book.setdefault(BookId(book_id), []).append(
                ReadingStretch(
                    start_time=start_time,
                    end_time=end_time,
                    start_page=start_page,
                    end_page=end_page,
                )
            )

        activity = self.activity_calculator.calculate(stretches_by_book, today, zone)
        if activity is None:
            return None

        stats = self.stats_calculator.calculate(
            [stretch for stretches in stretches_by_book.values() for stretch in stretches],
            activity,
            today,
            zone,
        )
        titles = await self._fetch_titles(
            user_id, {book_id for day in activity.days for book_id in day.book_ids}
        )
        return LibraryReadingActivityView(activity=activity, stats=stats, titles=titles)

    async def _fetch_sessions(self, user_id: UserId) -> Sequence[SessionRow]:
        """Load every session of the reader's, with the book it belongs to, oldest first.

        Every session rather than a windowed slice: which year the grid covers
        is the calculator's to decide, and it decides it from the last day the
        reader read -- which a window narrowed here could have cut off.

        A column list rather than the ORM entity: ``ReadingSession.highlights``
        is ``lazy="selectin"`` and the grid renders none of them.
        """
        stmt = (
            select(
                ReadingSessionORM.book_id,
                ReadingSessionORM.start_time,
                ReadingSessionORM.end_time,
                ReadingSessionORM.start_page,
                ReadingSessionORM.end_page,
            )
            .where(ReadingSessionORM.user_id == user_id.value)
            .order_by(ReadingSessionORM.start_time)
        )
        return (await self.db.execute(stmt)).tuples().all()

    async def _fetch_titles(
        self, user_id: UserId, book_ids: Collection[BookId]
    ) -> dict[BookId, str]:
        """Name the books the grid drew, and only those, alphabetically.

        Scoped by user as well as by id: the ids come from the reader's own
        sessions, and reading titles through the same filter keeps that true of
        every select here rather than only of the first.
        """
        if not book_ids:
            return {}

        stmt = (
            select(BookORM.id, BookORM.title)
            .where(
                BookORM.id.in_([book_id.value for book_id in book_ids]),
                BookORM.user_id == user_id.value,
            )
            .order_by(BookORM.title)
        )
        rows = (await self.db.execute(stmt)).tuples().all()
        return {BookId(book_id): title for book_id, title in rows}
