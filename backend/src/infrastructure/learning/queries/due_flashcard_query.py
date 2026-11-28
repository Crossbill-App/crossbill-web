"""Query adapter for the queue of Due Flashcards.

The filter and the order restate two domain definitions in SQL, under the same
names: ``is_due`` (``src/domain/learning/services/due_flashcards.py``) and
``ReviewState.retrievability_key``. A test pins the queue to both.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, case, func, literal, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.learning.queries.flashcards_in_context import FlashcardInContextPageView
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus
from src.infrastructure.common.sql import is_postgres
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.learning.queries.flashcard_in_context_rows import (
    flashcard_in_context_page,
)

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
        return await flashcard_in_context_page(
            self.db,
            user_id,
            book_id,
            _is_due(now),
            limit,
            offset,
            order_first_by=(
                case((FlashcardORM.due.is_(None), 1), else_=0),
                self._retrievability_key(now).desc(),
            ),
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
