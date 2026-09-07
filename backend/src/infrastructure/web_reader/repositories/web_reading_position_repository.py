"""Domain-centric repository for the web reader's stored reading positions."""

from datetime import datetime
from typing import Any

from sqlalchemy import case, literal, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable
from sqlalchemy.sql.elements import Case, ColumnElement

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
    WebReadingPositionORM.recorded_at,
)

# One returned row, in the order `_RETURNED` names the columns.
PositionRow = tuple[
    int, int, int, dict[str, Any], str, list[int] | None, int | None, datetime, datetime
]


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
        moved = {
            "locator": dict(position.locator),
            "xpoint": position.xpoint.to_string(),
            "position": position.position.to_json() if position.position else None,
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
            moved=moved,
            written_at=position.updated_at,
        )
        row = (await self.db.execute(stmt)).tuples().first()
        await self.db.commit()
        if row is None:
            return None
        stored = _row_to_domain(row)
        return RecordedPosition(
            position=stored,
            was_open=stored.reading_session_id,
            advanced=stored.recorded_at == as_aware(position.recorded_at),
        )

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


def _record_statement(
    dialect: str, values: dict[str, Any], moved: dict[str, Any], written_at: datetime
) -> Executable:
    """The one statement a position write is, with its two questions in it.

    Both dialects spell the upsert the same way and both return rows from it;
    only the constructor differs, because ``ON CONFLICT`` is an extension rather
    than core SQL.

    Two conditions, not one, because they answer different questions:

    - ``WHERE updated_at < :written_at`` is *may this write happen at all* --
      settled on arrival, so a device with a slow clock is never locked out.
    - the ``CASE`` on each moved column is *does this write move the position* --
      settled on the reader's own clock, so a tab that has been idling on page
      20 cannot overwrite the page 100 another tab reached, however freshly its
      closing write arrives. The write still lands: ``updated_at`` moves, the
      caller goes on to extend or close the reading session, and the newer
      position stays where it is.

    ``reading_session_id`` is in neither set: it is claimed separately by
    :meth:`WebReadingPositionRepository.attach_session`, once the session it
    should point at exists.
    """
    insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
    advances = moved["recorded_at"] > WebReadingPositionORM.recorded_at
    return (
        insert(WebReadingPositionORM)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["user_id", "book_id"],
            set_={
                "updated_at": written_at,
                **{
                    name: _kept_unless_advanced(name, value, advances)
                    for name, value in moved.items()
                },
            },
            where=WebReadingPositionORM.updated_at < written_at,
        )
        .returning(*_RETURNED)
    )


def _kept_unless_advanced(name: str, value: object, advances: ColumnElement[bool]) -> Case[Any]:
    """Write ``value`` into the column only when this observation is the newer one.

    The literal is given the column's own type. Without it the JSON column's
    dict is bound as a bare parameter that the driver has no way to render, and
    the write dies at the wire rather than in anything that reads like a bug.
    """
    column = WebReadingPositionORM.__table__.c[name]
    return case((advances, literal(value, type_=column.type)), else_=column)


def _row_to_domain(row: PositionRow) -> WebReadingPosition:
    """Reconstitute the aggregate from its row.

    ``updated_at`` is read back as UTC-aware whatever the dialect returned: on
    SQLite a ``DateTime(timezone=True)`` column comes back with no zone at all,
    and this value is compared against the server clock.
    """
    id_, user_id, book_id, locator, xpoint, position, session_id, updated_at, recorded_at = row
    return WebReadingPosition(
        id=WebReadingPositionId(id_),
        user_id=UserId(user_id),
        book_id=BookId(book_id),
        locator=locator,
        xpoint=XPoint.parse(xpoint),
        updated_at=as_aware(updated_at),
        recorded_at=as_aware(recorded_at),
        position=Position.from_json(position) if position else None,
        reading_session_id=ReadingSessionId(session_id) if session_id else None,
    )
