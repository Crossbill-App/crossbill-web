"""Query adapter for the highlight-label lists.

The label a style resolves to is a domain rule with a six-step precedence
chain, so the book list delegates it to ``LabelResolutionService`` rather than
restating it as a ``CASE``. What the adapter does own is the counting: the old
path issued one ``count_highlights_by_style`` per style, so a book with twenty
labels cost twenty round trips. Here it is one grouped count.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.queries.highlight_labels import HighlightLabelView
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.reading.orm.highlight_style_model import HighlightStyle as HighlightStyleORM


class HighlightLabelQuery:
    """Serves both highlight-label lists."""

    def __init__(self, db: AsyncSession, label_resolution_service: LabelResolutionService) -> None:
        self.db = db
        self.label_resolution_service = label_resolution_service

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[HighlightLabelView, ...] | None:
        """Return a book's resolved labels, or ``None`` if the user has no such book."""
        if not await self._owns_book(book_id, user_id):
            return None

        resolved_labels = await self.label_resolution_service.resolve_combination_labels(
            user_id, book_id
        )
        counts = await self._count_highlights_by_style(
            [style.id.value for style, _ in resolved_labels]
        )
        return tuple(
            HighlightLabelView(
                id=style.id.value,
                device_color=style.device_color,
                device_style=style.device_style,
                label=resolved.label,
                ui_color=resolved.ui_color,
                label_source=resolved.source,
                highlight_count=counts.get(style.id.value, 0),
            )
            for style, resolved in resolved_labels
        )

    async def list_global(self, user_id: UserId) -> tuple[HighlightLabelView, ...]:
        """Return the user's global default labels.

        Global styles are their own label source and carry no highlight count:
        highlights point at book-scoped styles, and this list has always
        reported ``0``.
        """
        stmt = select(
            HighlightStyleORM.id,
            HighlightStyleORM.device_color,
            HighlightStyleORM.device_style,
            HighlightStyleORM.label,
            HighlightStyleORM.ui_color,
        ).where(
            HighlightStyleORM.user_id == user_id.value,
            HighlightStyleORM.book_id.is_(None),
        )
        rows = (await self.db.execute(stmt)).all()
        return tuple(
            HighlightLabelView(
                id=row.id,
                device_color=row.device_color,
                device_style=row.device_style,
                label=row.label,
                ui_color=row.ui_color,
                label_source="global",
                highlight_count=0,
            )
            for row in rows
        )

    async def _owns_book(self, book_id: BookId, user_id: UserId) -> bool:
        """Report whether the book exists and belongs to the user."""
        stmt = select(BookORM.id).where(
            BookORM.id == book_id.value,
            BookORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).first() is not None

    async def _count_highlights_by_style(self, style_ids: list[int]) -> dict[int, int]:
        """Count each style's live highlights in one pass.

        Counting is deliberately not scoped to the book or the user: a style
        belongs to exactly one book already, and that is the number the old
        per-style count reported.
        """
        if not style_ids:
            return {}
        stmt = (
            select(HighlightORM.highlight_style_id, func.count(HighlightORM.id))
            .where(
                HighlightORM.highlight_style_id.in_(style_ids),
                HighlightORM.deleted_at.is_(None),
            )
            .group_by(HighlightORM.highlight_style_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {style_id: count for style_id, count in rows if style_id is not None}
