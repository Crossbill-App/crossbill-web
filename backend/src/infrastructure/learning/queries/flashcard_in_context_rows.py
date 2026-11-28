"""The select, book order and row mapping that every review flashcard list shares."""

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from sqlalchemy import ColumnElement, Row, Select, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.learning.queries.review_flashcards import (
    ReviewFlashcardPageView,
    ReviewFlashcardView,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.common.queries.row_mappers import flashcard_ref
from src.infrastructure.learning.mappers.flashcard_mapper import review_state_from_row
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM


async def review_flashcard_page(
    db: AsyncSession,
    user_id: UserId,
    book_id: BookId | None,
    where: Sequence[ColumnElement[bool]],
    limit: int,
    offset: int,
    order_first_by: Sequence[ColumnElement[Any]] = (),
) -> ReviewFlashcardPageView:
    """Return a page of the user's flashcards matching ``where`` and how many match in all.

    The page is in book order (one book at a time, by chapter, chapterless
    last), after any ``order_first_by`` keys.
    """
    filters = [FlashcardORM.user_id == user_id.value, *where]
    if book_id is not None:
        filters.append(FlashcardORM.book_id == book_id.value)
    rows = (await db.execute(_page(filters, order_first_by).offset(offset).limit(limit))).all()
    total = await db.scalar(select(func.count(FlashcardORM.id)).where(*filters))
    return ReviewFlashcardPageView(
        flashcards=tuple(_review_flashcard_view(row) for row in rows), total=total or 0
    )


def _page(
    filters: list[ColumnElement[bool]], order_first_by: Sequence[ColumnElement[Any]]
) -> Select[Any]:
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
            *order_first_by,
            FlashcardORM.book_id,
            case((ChapterORM.chapter_number.is_(None), 1), else_=0),
            ChapterORM.chapter_number,
            FlashcardORM.created_at,
            FlashcardORM.id,
        )
    )


def _review_flashcard_view(row: Row[Any]) -> ReviewFlashcardView:
    card, book_title, chapter_name, highlight_text, note_title = row
    return ReviewFlashcardView(
        **asdict(flashcard_ref(card)),
        book_title=book_title,
        chapter_name=chapter_name,
        highlight_text=highlight_text,
        note_title=note_title,
        review_state=review_state_from_row(card),
    )
