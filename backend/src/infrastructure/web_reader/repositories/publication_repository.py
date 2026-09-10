"""Repository for the publication index stored beside a book."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.web_reader.mappers.publication_json import (
    publication_from_json,
    publication_to_json,
)
from src.infrastructure.web_reader.orm.book_publication_model import (
    BookPublication as BookPublicationORM,
)


class PublicationRepository:
    """Repository implementation for stored publication indexes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, book_id: BookId, user_id: UserId) -> ParsedPublication | None:
        """Read a book's stored index, or ``None`` when there is none to read.

        A book someone else owns reads as absent rather than as an error: the
        caller may not learn that the row exists.
        """
        stmt = (
            select(BookPublicationORM)
            .join(BookORM, BookPublicationORM.book_id == BookORM.id)
            .where(BookPublicationORM.book_id == book_id.value)
            .where(BookORM.user_id == user_id.value)
        )
        result = await self.db.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return publication_from_json(orm.publication, orm.content_hash)

    async def save(self, book_id: BookId, file_name: str, publication: ParsedPublication) -> None:
        """Store a book's index, replacing whatever was derived from an earlier file."""
        orm = await self.db.get(BookPublicationORM, book_id.value)
        if orm is None:
            orm = BookPublicationORM(book_id=book_id.value)
            self.db.add(orm)
        orm.file_name = file_name
        orm.content_hash = publication.content_hash
        orm.publication = publication_to_json(publication)
        orm.derived_at = datetime.now(UTC)
        await self.db.commit()

    async def delete(self, book_id: BookId) -> None:
        """Drop a book's stored index if it has one."""
        orm = await self.db.get(BookPublicationORM, book_id.value)
        if orm is not None:
            await self.db.delete(orm)
            await self.db.commit()
