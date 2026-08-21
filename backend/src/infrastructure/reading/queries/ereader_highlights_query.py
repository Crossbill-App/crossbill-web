"""Query adapter for the ereader's highlight list.

The device needs a highlight's text, where it sits in the book and how it was
drawn -- three tables, none of which it wants as an aggregate. One select with
two outer joins covers it, and ``placeable`` is derived in Python from the
xpoints the row already carries.
"""

from sqlalchemy import nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.queries.ereader_highlights import EreaderHighlightView
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.reading.orm.highlight_style_model import (
    HighlightStyle as HighlightStyleORM,
)


class EreaderHighlightsQuery:
    """Serves the ereader highlight list from one join per book."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[EreaderHighlightView, ...]:
        """Return the book's device-visible highlights, oldest position first.

        Two states withhold a highlight here. Soft deletion takes it off the web
        as well; removal from devices keeps it on the web, with its flashcards
        and bookmarks, and only stops it reaching e-readers.

        The statement is built here rather than at module scope: adapters are
        imported early enough that resolving relationships at import time would
        configure the mappers before every model is registered.

        Highlights are ordered by page rather than by ``position``: position is
        a JSON column, which PostgreSQL cannot order by at all. Page is null for
        highlights the device sent without one, and those sort last, then by the
        device's own datetime, then by id so the order is total.
        """
        stmt = (
            select(
                HighlightORM.id,
                HighlightORM.text,
                HighlightORM.start_xpoint,
                HighlightORM.end_xpoint,
                HighlightORM.datetime,
                HighlightORM.koreader_updated_at,
                HighlightORM.page,
                HighlightORM.koreader_note,
                HighlightORM.origin_device_id,
                ChapterORM.chapter_number,
                ChapterORM.name.label("chapter_name"),
                HighlightStyleORM.device_color,
                HighlightStyleORM.device_style,
            )
            .outerjoin(ChapterORM, ChapterORM.id == HighlightORM.chapter_id)
            .outerjoin(HighlightStyleORM, HighlightStyleORM.id == HighlightORM.highlight_style_id)
            .where(
                HighlightORM.book_id == book_id.value,
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
                HighlightORM.removed_from_devices_at.is_(None),
            )
            .order_by(nulls_last(HighlightORM.page), HighlightORM.datetime, HighlightORM.id)
        )
        rows = (await self.db.execute(stmt)).all()
        return tuple(
            EreaderHighlightView(
                id=row.id,
                text=row.text,
                start_xpoint=row.start_xpoint,
                end_xpoint=row.end_xpoint,
                datetime=row.datetime,
                datetime_updated=row.koreader_updated_at,
                page=row.page,
                chapter_number=row.chapter_number,
                chapter_name=row.chapter_name,
                device_color=row.device_color,
                device_style=row.device_style,
                note=row.koreader_note,
                origin_device_id=row.origin_device_id,
                placeable=row.start_xpoint is not None and row.end_xpoint is not None,
            )
            for row in rows
        )
