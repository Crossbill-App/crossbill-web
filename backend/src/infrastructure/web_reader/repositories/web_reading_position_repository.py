"""Domain-centric repository for the web reader's stored reading positions."""

from datetime import datetime
from typing import Any

from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import RowMapping
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

# The columns a write reads back.
_RETURNED = (
    WebReadingPositionORM.id,
    WebReadingPositionORM.user_id,
    WebReadingPositionORM.book_id,
    WebReadingPositionORM.locator,
    WebReadingPositionORM.xpoint,
    WebReadingPositionORM.position,
    WebReadingPositionORM.locator_source_hash,
    WebReadingPositionORM.reading_session_id,
    WebReadingPositionORM.updated_at,
    WebReadingPositionORM.recorded_at,
)

# The columns a write moves only when it is the newer sighting.
_MOVED = ("locator", "xpoint", "position", "locator_source_hash", "recorded_at")


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
        row = (await self.db.execute(stmt)).mappings().first()
        return _row_to_domain(row) if row else None

    async def record(self, position: WebReadingPosition) -> RecordedPosition | None:
        """Store the position if it is the newest one, in one upsert.

        No decision is taken between reading the row and writing it: an insert
        that becomes an update on conflict, whose update is itself conditional
        on this observation being the newer one, cannot be raced into a
        duplicate-key error or into overwriting a newer position with an older.

        ``reading_session_id`` is left alone by the update, so the row that comes
        back carries the session that was open *before* this write -- which is
        what the caller needs to decide whether it is continuing that sitting.
        """
        moved = {
            "locator": dict(position.locator),
            "xpoint": position.xpoint.to_string(),
            "position": position.position.to_json() if position.position else None,
            "locator_source_hash": position.locator_source_hash,
            "recorded_at": position.recorded_at,
        }
        stmt = _record_statement(
            self.db.bind.dialect.name,
            values={
                "user_id": position.user_id.value,
                "book_id": position.book_id.value,
                "reading_session_id": None,
                "updated_at": position.updated_at,
                **moved,
            },
            written_at=position.updated_at,
        )
        row = (await self.db.execute(stmt)).mappings().first()
        await self.db.commit()
        if row is None:
            return None
        stored = _row_to_domain(row)
        return RecordedPosition(
            position=stored,
            advanced=stored.recorded_at == as_aware(position.recorded_at),
        )

    async def attach_session(
        self, position: WebReadingPosition, session_id: ReadingSessionId | None
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
                WebReadingPositionORM.updated_at == position.updated_at,
            )
            .values(reading_session_id=session_id.value if session_id else None)
        )
        await self.db.execute(stmt)
        await self.db.commit()


def _record_statement(dialect: str, values: dict[str, Any], written_at: datetime) -> Executable:
    """The one statement a position write is, weighing both clocks at once.

    Which clock settles what, and why one field cannot do both, is
    :class:`WebReadingPosition`'s docstring.
    """
    insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
    stmt = insert(WebReadingPositionORM).values(**values)
    advances = stmt.excluded.recorded_at >= WebReadingPositionORM.recorded_at
    return stmt.on_conflict_do_update(
        index_elements=["user_id", "book_id"],
        set_={
            "updated_at": written_at,
            **{
                name: case(
                    (advances, stmt.excluded[name]),
                    else_=WebReadingPositionORM.__table__.c[name],
                )
                for name in _MOVED
            },
        },
        where=WebReadingPositionORM.updated_at < written_at,
    ).returning(*_RETURNED)


def _row_to_domain(row: RowMapping) -> WebReadingPosition:
    """Reconstitute the aggregate from its row.

    Both timestamps are read back as UTC-aware whatever the dialect returned: on
    SQLite a ``DateTime(timezone=True)`` column comes back with no zone at all,
    and these values are compared against clocks that carry one.
    """
    session_id = row["reading_session_id"]
    position = row["position"]
    return WebReadingPosition(
        id=WebReadingPositionId(row["id"]),
        user_id=UserId(row["user_id"]),
        book_id=BookId(row["book_id"]),
        locator=row["locator"],
        xpoint=XPoint.parse(row["xpoint"]),
        locator_source_hash=row["locator_source_hash"],
        updated_at=as_aware(row["updated_at"]),
        recorded_at=as_aware(row["recorded_at"]),
        position=Position.from_json(position) if position else None,
        reading_session_id=ReadingSessionId(session_id) if session_id else None,
    )
