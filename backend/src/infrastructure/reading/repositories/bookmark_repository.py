"""Repository for Bookmark domain entities."""

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, HighlightId, UserId
from src.domain.reading.entities.bookmark import Bookmark
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.mappers.bookmark_mapper import BookmarkMapper
from src.infrastructure.reading.orm.bookmark_model import Bookmark as BookmarkORM


class BookmarkRepository(BaseRepository[Bookmark, BookmarkORM]):
    """Repository for Bookmark domain entities.

    Bookmarks carry no ``user_id`` column, so ownership is enforced through a
    join to the owning book (see :meth:`_ownership_filter`). ``delete`` is
    inherited from :class:`BaseRepository`; ``save`` is overridden because
    bookmarks are immutable.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.mapper = BookmarkMapper()
        super().__init__(db, BookmarkORM, self.mapper)

    def _ownership_filter(self, stmt: Select[Any], user_id: UserId) -> Select[Any]:
        """Scope bookmarks to their owner via the book they belong to."""
        return stmt.join(BookORM, BookmarkORM.book_id == BookORM.id).where(
            BookORM.user_id == user_id.value
        )

    async def find_by_book_and_highlight(
        self, book_id: BookId, highlight_id: HighlightId
    ) -> Bookmark | None:
        """
        Find a bookmark by book and highlight.

        Args:
            book_id: The book ID
            highlight_id: The highlight ID

        Returns:
            Bookmark entity if found, None otherwise
        """
        stmt = select(BookmarkORM).where(
            BookmarkORM.book_id == book_id.value,
            BookmarkORM.highlight_id == highlight_id.value,
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return self.mapper.to_domain(orm_model) if orm_model else None

    async def save(self, bookmark: Bookmark) -> Bookmark:
        """
        Save a bookmark entity.

        Args:
            bookmark: The bookmark entity to save

        Returns:
            Saved bookmark entity with database-generated values
        """
        if bookmark.id.value == 0:
            # Create new
            orm_model = self.mapper.to_orm(bookmark)
            self.db.add(orm_model)
            await self.db.commit()
            await self.db.refresh(orm_model)
            return self.mapper.to_domain(orm_model)
        # Bookmarks are immutable - no update case
        raise ValueError("Bookmarks cannot be updated")
