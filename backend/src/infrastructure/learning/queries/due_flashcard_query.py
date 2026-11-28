"""Query adapter for the queue of Due Flashcards.

The filter and the order restate two domain definitions in SQL, under the same
names: ``is_due`` (``src/domain/learning/services/due_flashcards.py``) and
``ReviewState.retrievability_key``. A test pins the queue to both.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.learning.queries.due_flashcards import DueFlashcardPageView
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus
from src.infrastructure.common.queries.row_mappers import flashcard_ref
from src.infrastructure.common.sql import is_postgres
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM

_UNIX_EPOCH_JULIAN_DAY = 2440587.5
_SECONDS_PER_DAY = 86400.0


class DueFlashcardQuery:
    """Serves the Due Flashcard queue from one ordered select and a count."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_due(
        self, user_id: UserId, now: datetime, book_id: BookId | None, limit: int, offset: int
    ) -> DueFlashcardPageView:
        """Return a page of the queue as it stands at ``now``."""
        filters = [FlashcardORM.user_id == user_id.value, *_is_due(now)]
        if book_id is not None:
            filters.append(FlashcardORM.book_id == book_id.value)
        rows = (
            (await self.db.execute(self._queue(filters, now).offset(offset).limit(limit)))
            .scalars()
            .all()
        )
        total = await self.db.scalar(select(func.count(FlashcardORM.id)).where(*filters))
        return DueFlashcardPageView(
            flashcards=tuple(flashcard_ref(row) for row in rows), total=total or 0
        )

    def _queue(
        self, filters: list[ColumnElement[bool]], now: datetime
    ) -> Select[tuple[FlashcardORM]]:
        chapter_id = func.coalesce(FlashcardORM.chapter_id, HighlightORM.chapter_id)
        is_new = FlashcardORM.due.is_(None)
        return (
            select(FlashcardORM)
            .outerjoin(HighlightORM, HighlightORM.id == FlashcardORM.highlight_id)
            .outerjoin(ChapterORM, ChapterORM.id == chapter_id)
            .where(*filters)
            .order_by(
                case((is_new, 1), else_=0),
                self._retrievability_key(now).desc(),
                FlashcardORM.book_id,
                case((ChapterORM.chapter_number.is_(None), 1), else_=0),
                ChapterORM.chapter_number,
                FlashcardORM.created_at,
                FlashcardORM.id,
            )
        )

    def _retrievability_key(self, now: datetime) -> ColumnElement[Any]:
        elapsed = literal(now.timestamp()) - self._last_review_epoch_seconds()
        return elapsed / FlashcardORM.stability

    def _last_review_epoch_seconds(self) -> ColumnElement[Any]:
        if is_postgres(self.db):
            return func.extract("epoch", FlashcardORM.last_review)
        return (
            func.julianday(FlashcardORM.last_review) - _UNIX_EPOCH_JULIAN_DAY
        ) * _SECONDS_PER_DAY


def _is_due(now: datetime) -> list[ColumnElement[bool]]:
    return [
        FlashcardORM.status == FlashcardStatus.ACTIVE.value,
        or_(FlashcardORM.due.is_(None), FlashcardORM.due <= now),
    ]
