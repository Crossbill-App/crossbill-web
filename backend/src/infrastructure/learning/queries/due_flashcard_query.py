"""Query adapter for the queue of Due Flashcards.

The filter and the order restate two domain definitions in SQL, under the same
names: ``is_due`` (``src/domain/learning/services/due_flashcards.py``) and
``ReviewState.retrievability_key``. A test pins the queue to both.
"""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Row, Select, and_, case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.learning.queries.due_flashcards import (
    FlashcardInContextPageView,
    FlashcardInContextView,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus
from src.infrastructure.common.queries.row_mappers import flashcard_ref
from src.infrastructure.common.sql import is_postgres
from src.infrastructure.learning.mappers.flashcard_mapper import review_state_from_row
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM

_UNIX_EPOCH_JULIAN_DAY = 2440587.5
_SECONDS_PER_DAY = 86400.0


class DueFlashcardQuery:
    """Serves the Due Flashcard queue from one ordered select and a count."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_due(
        self, user_id: UserId, now: datetime, book_id: BookId | None, limit: int, offset: int
    ) -> FlashcardInContextPageView:
        """Return a page of the queue as it stands at ``now``."""
        filters = [FlashcardORM.user_id == user_id.value, *_is_due(now)]
        if book_id is not None:
            filters.append(FlashcardORM.book_id == book_id.value)
        page = self._queue(filters, now).offset(offset).limit(limit)
        rows = (await self.db.execute(page)).all()
        total = await self.db.scalar(select(func.count(FlashcardORM.id)).where(*filters))
        return FlashcardInContextPageView(
            flashcards=tuple(_flashcard_in_context_view(row) for row in rows), total=total or 0
        )

    def _queue(self, filters: list[ColumnElement[bool]], now: datetime) -> Select[Any]:
        return (
            select(FlashcardORM, BookORM.title, ChapterORM.name, HighlightORM.text, NoteORM.title)
            .join(BookORM, BookORM.id == FlashcardORM.book_id)
            .outerjoin(
                HighlightORM,
                and_(
                    HighlightORM.id == FlashcardORM.highlight_id,
                    HighlightORM.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                ChapterORM,
                ChapterORM.id == func.coalesce(FlashcardORM.chapter_id, HighlightORM.chapter_id),
            )
            .outerjoin(NoteORM, NoteORM.id == FlashcardORM.note_id)
            .where(*filters)
            .order_by(
                case((FlashcardORM.due.is_(None), 1), else_=0),
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


def _flashcard_in_context_view(row: Row[Any]) -> FlashcardInContextView:
    card, book_title, chapter_name, highlight_text, note_title = row
    return FlashcardInContextView(
        **asdict(flashcard_ref(card)),
        book_title=book_title,
        chapter_name=chapter_name,
        highlight_text=highlight_text,
        note_title=note_title,
        review_state=review_state_from_row(card),
    )
