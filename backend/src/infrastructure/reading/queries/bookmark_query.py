"""Query adapter for a book's bookmark list.

Bookmarks carry no ``user_id`` column, so ownership runs through the book they
hang off. One select answers both questions the view asks -- does this user own
the book, and what is pinned in it -- instead of a repository round trip per
question.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.queries.bookmarks import BookmarkView
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.bookmark_model import Bookmark as BookmarkORM


class BookmarkQuery:
    """Serves the bookmark list from a single select over the owning book."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[BookmarkView, ...] | None:
        """Return the book's bookmarks newest first, or ``None`` if the user has no such book."""
        if not await self._owns_book(book_id, user_id):
            return None

        stmt = (
            select(
                BookmarkORM.id,
                BookmarkORM.book_id,
                BookmarkORM.highlight_id,
                BookmarkORM.created_at,
            )
            .where(BookmarkORM.book_id == book_id.value)
            .order_by(BookmarkORM.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).all()
        return tuple(
            BookmarkView(
                id=row.id,
                book_id=row.book_id,
                highlight_id=row.highlight_id,
                created_at=row.created_at,
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
