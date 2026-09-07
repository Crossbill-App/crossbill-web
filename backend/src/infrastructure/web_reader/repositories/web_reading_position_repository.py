"""Domain-centric repository for the web reader's stored reading positions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.web_reader.orm.web_reading_position_model import (
    WebReadingPosition as WebReadingPositionORM,
)


class WebReadingPositionRepository:
    """Persistence for :class:`WebReadingPosition`, keyed by reader and book."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_for_book(self, book_id: BookId, user_id: UserId) -> WebReadingPosition | None:
        """Return where this reader last was in this book, or ``None`` if never here."""
        orm = await self._fetch(book_id, user_id)
        return self._to_domain(orm) if orm else None

    async def save(self, position: WebReadingPosition) -> WebReadingPosition:
        """Insert the position or update the row already stored for its book."""
        orm = await self._fetch(position.book_id, position.user_id)
        if orm is None:
            orm = WebReadingPositionORM(id=orm_id(position.id))
        orm.user_id = position.user_id.value
        orm.book_id = position.book_id.value
        orm.locator = dict(position.locator)
        orm.xpoint = position.xpoint.to_string()
        orm.position = position.position.to_json() if position.position else None
        orm.reading_session_id = (
            position.reading_session_id.value if position.reading_session_id else None
        )
        orm.updated_at = position.updated_at
        self.db.add(orm)
        await self.db.commit()
        await self.db.refresh(orm)
        return self._to_domain(orm)

    async def _fetch(self, book_id: BookId, user_id: UserId) -> WebReadingPositionORM | None:
        """Load the one row a reader may have for a book."""
        stmt = select(WebReadingPositionORM).where(
            WebReadingPositionORM.book_id == book_id.value,
            WebReadingPositionORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def _to_domain(self, orm: WebReadingPositionORM) -> WebReadingPosition:
        """Reconstitute the aggregate from its row.

        ``updated_at`` is read back as UTC-aware whatever the dialect returned:
        the aggregate compares it against the moment a write claims, and on
        SQLite a ``DateTime(timezone=True)`` column comes back with no zone at
        all.
        """
        return WebReadingPosition(
            id=WebReadingPositionId(orm.id),
            user_id=UserId(orm.user_id),
            book_id=BookId(orm.book_id),
            locator=orm.locator,
            xpoint=XPoint.parse(orm.xpoint),
            updated_at=as_aware(orm.updated_at),
            position=Position.from_json(orm.position) if orm.position else None,
            reading_session_id=(
                ReadingSessionId(orm.reading_session_id) if orm.reading_session_id else None
            ),
        )
