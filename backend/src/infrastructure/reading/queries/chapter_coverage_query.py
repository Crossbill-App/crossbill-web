"""Query adapter for Chapter Coverage.

The adapter selects the chapters' starts, the book's length and every Page View
of the book; ``measure_chapter_coverage`` decides what they add up to.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, ChapterId, UserId
from src.domain.reading.services.chapter_coverage import (
    ChapterCoverage,
    ChapterStart,
    CharacterRange,
    PageViewSpan,
    measure_chapter_coverage,
)
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.reading.orm.page_view_model import PageView as PageViewORM
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM


class ChapterCoverageQuery:
    """Serves Chapter Coverage from three targeted selects."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_chapter_coverage(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[ChapterCoverage, ...]:
        """Return the coverage of every chapter of a user's book, in reading order."""
        return measure_chapter_coverage(
            await self._fetch_chapter_starts(book_id, user_id),
            await self._fetch_total_characters(book_id, user_id),
            await self._fetch_page_view_spans(book_id, user_id),
        )

    async def _fetch_chapter_starts(self, book_id: BookId, user_id: UserId) -> list[ChapterStart]:
        stmt = (
            select(ChapterORM.id, ChapterORM.start_offset)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(BookORM.id == book_id.value, BookORM.user_id == user_id.value)
            .order_by(ChapterORM.chapter_number.nulls_last(), ChapterORM.id)
        )
        rows = (await self.db.execute(stmt)).all()
        return [ChapterStart(ChapterId(row.id), row.start_offset) for row in rows]

    async def _fetch_total_characters(self, book_id: BookId, user_id: UserId) -> int | None:
        stmt = select(BookORM.total_characters).where(
            BookORM.id == book_id.value, BookORM.user_id == user_id.value
        )
        return await self.db.scalar(stmt)

    async def _fetch_page_view_spans(self, book_id: BookId, user_id: UserId) -> list[PageViewSpan]:
        stmt = (
            select(PageViewORM.start_offset, PageViewORM.end_offset, PageViewORM.duration_ms)
            .join(ReadingSessionORM, ReadingSessionORM.id == PageViewORM.reading_session_id)
            .where(
                ReadingSessionORM.book_id == book_id.value,
                ReadingSessionORM.user_id == user_id.value,
            )
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            PageViewSpan(
                CharacterRange(row.start_offset, row.end_offset),
                timedelta(milliseconds=row.duration_ms),
            )
            for row in rows
        ]
