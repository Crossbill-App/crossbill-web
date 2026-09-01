"""Query adapter for the reader's whole library on one activity grid.

Gathers the sessions a grid could be drawn from, hands them to the two
calculators, and names the books that ended up on it. Nothing here decides which
day a session belongs to, how dark a square is, or what a streak means.
"""

from collections.abc import Collection, Sequence
from datetime import date, timedelta, tzinfo
from datetime import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.queries.library_reading_activity import (
    ActivityBookView,
    LibraryReadingActivityView,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.library_reading_activity_calculator import (
    LibraryReadingActivityCalculator,
)
from src.domain.reading.services.library_reading_stats_calculator import (
    LibraryReadingStatsCalculator,
)
from src.domain.reading.services.reading_activity_calculator import WINDOW_DAYS
from src.domain.reading.services.reading_stretch import ReadingStretch, day_in
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM

SessionRow = tuple[int, dt, dt, int | None, int | None]

DATE_LINE_SLACK = timedelta(days=1)
"""A day either side of the bound, so no timezone can put a session outside it."""


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
        last_read = await self._fetch_last_session_start(user_id)
        if last_read is None:
            return None

        stretches_by_book: dict[BookId, list[ReadingStretch]] = {}
        for book_id, start_time, end_time, start_page, end_page in await self._fetch_sessions(
            user_id, self._earliest_of_interest(day_in(last_read, zone), today)
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

        stats = self.stats_calculator.calculate(stretches_by_book, activity, today, zone)
        books = await self._fetch_books(
            user_id, {book_id for day in activity.days for book_id in day.book_ids}
        )
        return LibraryReadingActivityView(activity=activity, stats=stats, books=books)

    def _earliest_of_interest(self, last_read: date, today: date) -> date:
        """The first day a session could still land on the grid.

        A bound, not the window: which day the grid ends on stays the
        calculator's to decide, from the sessions this lets through.
        """
        return min(last_read, today) - timedelta(days=WINDOW_DAYS - 1) - DATE_LINE_SLACK

    async def _fetch_last_session_start(self, user_id: UserId) -> dt | None:
        """When the reader last sat down, or ``None`` if they never have.

        Asked on its own because it is all the window's end depends on, and it
        costs one row rather than a decade of them.
        """
        stmt = select(func.max(ReadingSessionORM.start_time)).where(
            ReadingSessionORM.user_id == user_id.value
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _fetch_sessions(self, user_id: UserId, since: date) -> Sequence[SessionRow]:
        """Load the reader's sessions from ``since`` on, with the book each belongs to.

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
            .where(
                ReadingSessionORM.user_id == user_id.value,
                ReadingSessionORM.start_time >= dt.combine(since, dt.min.time()),
            )
            .order_by(ReadingSessionORM.start_time)
        )
        return (await self.db.execute(stmt)).tuples().all()

    async def _fetch_books(
        self, user_id: UserId, book_ids: Collection[BookId]
    ) -> tuple[ActivityBookView, ...]:
        """Name the books the grid drew, and only those, alphabetically.

        Scoped by user as well as by id, so every select here is filtered the
        same way rather than only the first.
        """
        if not book_ids:
            return ()

        stmt = (
            select(BookORM.id, BookORM.title)
            .where(
                BookORM.id.in_([book_id.value for book_id in book_ids]),
                BookORM.user_id == user_id.value,
            )
            .order_by(BookORM.title)
        )
        rows = (await self.db.execute(stmt)).tuples().all()
        return tuple(ActivityBookView(id=BookId(book_id), title=title) for book_id, title in rows)
