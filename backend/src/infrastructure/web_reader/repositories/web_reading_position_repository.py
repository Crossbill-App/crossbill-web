"""Domain-centric repository for the web reader's stored reading positions."""

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from src.application.web_reader.protocols.web_reading_position_repository import RecordedPosition
from src.domain.common.time import as_aware
from src.domain.common.value_objects import (
    BookId,
    ReadingSessionId,
    UserId,
    WebReadingPositionId,
    XPoint,
)
from src.domain.common.value_objects.position import Position
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition
from src.infrastructure.web_reader.orm.web_reading_position_model import (
    WebReadingPosition as WebReadingPositionORM,
)

# The columns a write reads back, in the order `_row_to_domain` unpacks them.
_RETURNED = (
    WebReadingPositionORM.id,
    WebReadingPositionORM.user_id,
    WebReadingPositionORM.book_id,
    WebReadingPositionORM.locator,
    WebReadingPositionORM.xpoint,
    WebReadingPositionORM.position,
    WebReadingPositionORM.reading_session_id,
    WebReadingPositionORM.updated_at,
)

# One returned row, in the order `_RETURNED` names the columns.
PositionRow = tuple[int, int, int, dict[str, Any], str, list[int] | None, int | None, datetime]


class WebReadingPositionRepository:
    """Persistence for :class:`WebReadingPosition`, keyed by reader and book."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_for_book(self, book_id: BookId, user_id: UserId) -> WebReadingPosition | None:
        """Return where this reader last was in this book, or ``None`` if never here."""
        stmt = select(*_RETURNED).where(
            WebReadingPositionORM.book_id == book_id.value,
            WebReadingPositionORM.user_id == user_id.value,
        )
        row = (await self.db.execute(stmt)).tuples().first()
        return _row_to_domain(row) if row else None

    async def record(self, position: WebReadingPosition) -> RecordedPosition | None:
        """Store the position if it is the newest one, in one upsert.

        The whole point is that no decision is taken between reading the row and
        writing it: an insert that becomes an update on conflict, whose update
        is itself conditional on this observation being newer than what is
        stored, cannot be raced into a duplicate-key error or into overwriting a
        newer position with an older one.

        ``reading_session_id`` is left alone by the update -- so the row that
        comes back carries the session that was open *before* this write, which
        is exactly what the caller needs in order to decide whether it is
        continuing that sitting.
        """
        written = {
            "locator": dict(position.locator),
            "xpoint": position.xpoint.to_string(),
            "position": position.position.to_json() if position.position else None,
            "updated_at": position.updated_at,
        }
        stmt = _record_statement(
            self.db.bind.dialect.name,
            values={
                "user_id": position.user_id.value,
                "book_id": position.book_id.value,
                "reading_session_id": None,
                **written,
            },
            written=written,
        )
        row = (await self.db.execute(stmt)).tuples().first()
        await self.db.commit()
        if row is None:
            return None
        stored = _row_to_domain(row)
        return RecordedPosition(position=stored, was_open=stored.reading_session_id)

    async def attach_session(
        self,
        position: WebReadingPosition,
        session_id: ReadingSessionId | None,
        recorded_at: datetime,
    ) -> None:
        """Point the row at its open session, only while this write is still the latest.

        The ``updated_at`` predicate is the whole guard: a writer that has been
        overtaken silently changes nothing, so a close cannot undo a page turn
        that landed after it and a page turn cannot reopen a session that was
        closed after it.
        """
        stmt = (
            update(WebReadingPositionORM)
            .where(
                WebReadingPositionORM.id == position.id.value,
                WebReadingPositionORM.updated_at == recorded_at,
            )
            .values(reading_session_id=session_id.value if session_id else None)
        )
        await self.db.execute(stmt)
        await self.db.commit()


def _record_statement(dialect: str, values: dict[str, Any], written: dict[str, Any]) -> Executable:
    """The one statement a position write is: insert, or update if this is newer.

    Both dialects spell the upsert the same way and both return rows from it;
    only the constructor differs, because ``ON CONFLICT`` is an extension rather
    than core SQL.

    ``written`` is the subset a conflict updates -- everything but the keys and
    the session pointer, which :meth:`attach_session` claims separately.
    """
    insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
    return (
        insert(WebReadingPositionORM)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["user_id", "book_id"],
            set_=written,
            where=WebReadingPositionORM.updated_at < written["updated_at"],
        )
        .returning(*_RETURNED)
    )


def _row_to_domain(row: PositionRow) -> WebReadingPosition:
    """Reconstitute the aggregate from its row.

    ``updated_at`` is read back as UTC-aware whatever the dialect returned: on
    SQLite a ``DateTime(timezone=True)`` column comes back with no zone at all,
    and this value is compared against the server clock.
    """
    id_, user_id, book_id, locator, xpoint, position, session_id, updated_at = row
    return WebReadingPosition(
        id=WebReadingPositionId(id_),
        user_id=UserId(user_id),
        book_id=BookId(book_id),
        locator=locator,
        xpoint=XPoint.parse(xpoint),
        updated_at=as_aware(updated_at),
        position=Position.from_json(position) if position else None,
        reading_session_id=ReadingSessionId(session_id) if session_id else None,
    )
