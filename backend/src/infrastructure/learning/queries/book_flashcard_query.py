"""Query adapter for a book's flashcard list.

Rows map straight to view DTOs: the old path loaded every card as a
``Flashcard`` aggregate and every linked highlight as a ``Highlight`` with its
``Chapter`` and ``Tag`` entities, only to render a handful of their fields. The
one rule-derived value here (a highlight's effective label) is delegated to
``LabelResolutionService`` rather than re-encoded in SQL.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, noload

from src.application.common.queries.highlight_row import HighlightLabelView
from src.application.learning.queries.book_flashcards import (
    FlashcardHighlightView,
    FlashcardWithHighlightView,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.infrastructure.common.queries.row_mappers import tag_ref
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM


class BookFlashcardQuery:
    """Serves the book-flashcards read model from purpose-built selects."""

    def __init__(self, db: AsyncSession, label_resolution_service: LabelResolutionService) -> None:
        self.db = db
        self.label_resolution_service = label_resolution_service

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[FlashcardWithHighlightView, ...]:
        """Return the user's flashcards for a book, newest first."""
        cards = await self._fetch_flashcards(book_id, user_id)
        if not cards:
            return ()

        highlight_ids = {card.highlight_id for card in cards if card.highlight_id is not None}
        highlights: dict[int, FlashcardHighlightView] = {}
        if highlight_ids:
            labels = await self.label_resolution_service.resolve_for_book(user_id, book_id)
            highlights = await self._fetch_highlights(highlight_ids, user_id, labels)

        return tuple(
            FlashcardWithHighlightView(
                id=card.id,
                user_id=card.user_id,
                book_id=card.book_id,
                highlight_id=card.highlight_id,
                chapter_id=card.chapter_id,
                note_id=card.note_id,
                question=card.question,
                answer=card.answer,
                highlight=highlights.get(card.highlight_id)
                if card.highlight_id is not None
                else None,
            )
            for card in cards
        )

    async def _fetch_flashcards(self, book_id: BookId, user_id: UserId) -> Sequence[FlashcardORM]:
        """Load the book's flashcards, newest first."""
        stmt = (
            select(FlashcardORM)
            .where(
                FlashcardORM.book_id == book_id.value,
                FlashcardORM.user_id == user_id.value,
            )
            .order_by(FlashcardORM.created_at.desc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def _fetch_highlights(
        self,
        highlight_ids: set[int],
        user_id: UserId,
        labels: dict[int, ResolvedLabel],
    ) -> dict[int, FlashcardHighlightView]:
        """Load the linked highlights the user owns that are not soft-deleted."""
        stmt = (
            select(HighlightORM)
            .options(
                joinedload(HighlightORM.chapter),
                joinedload(HighlightORM.tags),
                # Highlight.reading_sessions is lazy="selectin" and unused here.
                noload(HighlightORM.reading_sessions),
            )
            .where(
                HighlightORM.id.in_(highlight_ids),
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
        )
        rows = (await self.db.execute(stmt)).unique().scalars().all()
        return {row.id: _highlight_view(row, labels) for row in rows}


def _highlight_view(row: HighlightORM, labels: dict[int, ResolvedLabel]) -> FlashcardHighlightView:
    """Map a highlight row and its eagerly loaded relations to the view DTO."""
    style_id = row.highlight_style_id
    resolved = labels.get(style_id) if style_id is not None else None
    return FlashcardHighlightView(
        id=row.id,
        book_id=row.book_id,
        chapter_id=row.chapter_id,
        chapter_name=row.chapter.name if row.chapter else None,
        chapter_number=row.chapter.chapter_number if row.chapter else None,
        text=row.text,
        page=row.page,
        datetime=row.datetime,
        label=HighlightLabelView(
            highlight_style_id=style_id,
            text=resolved.label if resolved else None,
            ui_color=resolved.ui_color if resolved else None,
        )
        if style_id is not None
        else None,
        tags=tuple(tag_ref(tag) for tag in row.tags),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
