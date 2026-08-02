"""Repository for ChapterDigest domain entities."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, ChapterDigestId, ChapterId
from src.domain.reading.entities.chapter_digest import (
    ChapterDigest,
)
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.reading.mappers.chapter_digest_mapper import (
    ChapterDigestMapper,
)
from src.infrastructure.reading.orm.chapter_digest_model import (
    ChapterDigest as ChapterDigestORM,
)


class ChapterDigestRepository:
    """Repository implementation for chapter digests."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.mapper = ChapterDigestMapper()

    async def find_by_id(self, id: ChapterDigestId) -> ChapterDigest | None:
        """Find a digest by ID."""
        stmt = select(ChapterDigestORM).where(ChapterDigestORM.id == id.value)
        result = await self.db.execute(stmt)
        orm = result.scalar_one_or_none()
        return self.mapper.to_domain(orm) if orm else None

    async def find_all_by_book_id(self, book_id: BookId) -> list[ChapterDigest]:
        """Find the digest of every chapter in a book."""
        stmt = (
            select(ChapterDigestORM)
            .join(ChapterORM, ChapterDigestORM.chapter_id == ChapterORM.id)
            .where(ChapterORM.book_id == book_id.value)
        )
        result = await self.db.execute(stmt)
        orms = result.scalars().all()
        return [self.mapper.to_domain(orm) for orm in orms]

    async def find_by_chapter_id(self, chapter_id: ChapterId) -> ChapterDigest | None:
        """Find a specific chapter's digest."""
        stmt = select(ChapterDigestORM).where(ChapterDigestORM.chapter_id == chapter_id.value)
        result = await self.db.execute(stmt)
        orm = result.scalar_one_or_none()
        return self.mapper.to_domain(orm) if orm else None

    async def save(self, content: ChapterDigest) -> ChapterDigest:
        """Save or update a digest."""
        existing = None
        if content.id.value != 0:
            existing = await self.db.get(ChapterDigestORM, content.id.value)

        if not existing:
            # Also check by chapter_id for upsert behavior
            stmt = select(ChapterDigestORM).where(
                ChapterDigestORM.chapter_id == content.chapter_id.value
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

        if existing:
            orm = self.mapper.to_orm(content, existing)
            await self.db.commit()
            await self.db.refresh(orm)
            return self.mapper.to_domain(orm)
        orm = self.mapper.to_orm(content)
        self.db.add(orm)
        await self.db.commit()
        await self.db.refresh(orm)
        return self.mapper.to_domain(orm)

    async def delete(self, id: ChapterDigestId) -> None:
        """Delete a digest by ID."""
        stmt = select(ChapterDigestORM).where(ChapterDigestORM.id == id.value)
        result = await self.db.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            await self.db.delete(orm)
            await self.db.commit()
