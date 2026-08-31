"""Query adapter for a book's reading-session list.

Every column the view renders comes from Postgres, so the adapter reaches for
``LabelResolutionService`` -- to reuse the label rule rather than re-encode it
in SQL -- and nothing else.
"""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from src.application.common.queries.highlight_row import HighlightLabelView
from src.application.reading.queries.reading_sessions import (
    ReadingSessionPageView,
    ReadingSessionView,
    SessionHighlightView,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.associations import reading_session_highlights
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM


class ReadingSessionQuery:
    """Serves the reading-session list from targeted selects."""

    def __init__(
        self,
        db: AsyncSession,
        label_resolution_service: LabelResolutionService,
    ) -> None:
        self.db = db
        self.label_resolution_service = label_resolution_service

    async def list_for_book(
        self, book_id: BookId, user_id: UserId, limit: int, offset: int
    ) -> ReadingSessionPageView | None:
        """Return a page of sessions newest first, or ``None`` if the user has no such book."""
        if not await self._book_exists(book_id, user_id):
            return None

        sessions = await self._fetch_sessions(book_id, user_id, limit, offset)
        total = await self._count_sessions(book_id, user_id)
        labels = await self.label_resolution_service.resolve_for_book(user_id, book_id)
        highlights = await self._fetch_highlights_by_session(
            [row.id for row in sessions], user_id, labels
        )

        return ReadingSessionPageView(
            sessions=tuple(
                ReadingSessionView(
                    id=row.id,
                    book_id=row.book_id,
                    device_id=row.device_id,
                    content_hash=row.content_hash,
                    start_time=row.start_time,
                    end_time=row.end_time,
                    start_page=row.start_page,
                    end_page=row.end_page,
                    created_at=row.created_at,
                    highlights=highlights.get(row.id, ()),
                )
                for row in sessions
            ),
            total=total,
        )

    async def _book_exists(self, book_id: BookId, user_id: UserId) -> bool:
        """Say whether the user has this book at all; the list is empty either way."""
        stmt = select(BookORM.id).where(
            BookORM.id == book_id.value,
            BookORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).first() is not None

    async def _fetch_sessions(
        self, book_id: BookId, user_id: UserId, limit: int, offset: int
    ) -> Sequence[ReadingSessionORM]:
        """Load one page of the book's sessions, newest first."""
        stmt = (
            select(ReadingSessionORM)
            # ReadingSession.highlights is lazy="selectin"; the view loads them
            # itself, scoped to the user and to live rows.
            .options(noload(ReadingSessionORM.highlights))
            .where(
                ReadingSessionORM.book_id == book_id.value,
                ReadingSessionORM.user_id == user_id.value,
            )
            .order_by(ReadingSessionORM.start_time.desc())
            .offset(offset)
            .limit(limit)
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def _count_sessions(self, book_id: BookId, user_id: UserId) -> int:
        """Count the book's sessions, ignoring the page window."""
        stmt = select(func.count(ReadingSessionORM.id)).where(
            ReadingSessionORM.book_id == book_id.value,
            ReadingSessionORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def _fetch_highlights_by_session(
        self,
        session_ids: list[int],
        user_id: UserId,
        labels: dict[int, ResolvedLabel],
    ) -> dict[int, tuple[SessionHighlightView, ...]]:
        """Load the live highlights of each session, in document order."""
        if not session_ids:
            return {}

        stmt = (
            select(reading_session_highlights.c.reading_session_id, HighlightORM)
            .join(HighlightORM, reading_session_highlights.c.highlight_id == HighlightORM.id)
            .options(
                # Both are lazy="selectin", and this list renders neither.
                noload(HighlightORM.tags),
                noload(HighlightORM.reading_sessions),
            )
            .where(
                reading_session_highlights.c.reading_session_id.in_(session_ids),
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
        )
        rows = (await self.db.execute(stmt)).all()

        grouped: dict[int, list[HighlightORM]] = defaultdict(list)
        for session_id, highlight in rows:
            grouped[session_id].append(highlight)

        return {
            session_id: tuple(
                _highlight_view(row, labels) for row in sorted(highlights, key=_document_order)
            )
            for session_id, highlights in grouped.items()
        }


def _document_order(row: HighlightORM) -> tuple[bool, Position]:
    """Order highlights by document position, positionless ones last."""
    if row.position is None:
        return (True, Position(index=0))
    return (False, Position.from_json(row.position))


def _highlight_view(row: HighlightORM, labels: dict[int, ResolvedLabel]) -> SessionHighlightView:
    """Map a session's highlight row to the view DTO."""
    style_id = row.highlight_style_id
    resolved = labels.get(style_id) if style_id is not None else None
    return SessionHighlightView(
        id=row.id,
        book_id=row.book_id,
        chapter_id=row.chapter_id,
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
        removed_from_devices=row.removed_from_devices_at is not None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
