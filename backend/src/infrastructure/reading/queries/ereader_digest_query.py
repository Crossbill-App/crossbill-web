"""Query adapter for the ereader's chapter-digest list.

The old path loaded a Book aggregate, then every Chapter aggregate of that
book, used the chapters only for their name, number and parent, and joined
them to the digest rows in Python. Here one join returns exactly the
chapters that have a digest, with the parent chapter's name alongside.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.application.reading.queries.ereader_digest import EreaderChapterDigestView
from src.domain.common.value_objects.ids import UserId
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.reading.orm.chapter_digest_model import (
    ChapterDigest as ChapterDigestORM,
)


class EreaderDigestQuery:
    """Serves the ereader digest list from one join per book."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_client_book(
        self, client_book_id: str, user_id: UserId
    ) -> tuple[EreaderChapterDigestView, ...] | None:
        """Return the chapters that have a digest, or ``None`` if no such book."""
        book_id = await self._resolve_book(client_book_id, user_id)
        if book_id is None:
            return None
        return await self._fetch_digest(book_id)

    async def _resolve_book(self, client_book_id: str, user_id: UserId) -> int | None:
        """Resolve the client-side book id to the user's book."""
        stmt = select(BookORM.id).where(
            BookORM.client_book_id == client_book_id,
            BookORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _fetch_digest(self, book_id: int) -> tuple[EreaderChapterDigestView, ...]:
        """Load each chapter that has a digest, with its parent chapter's name.

        The statement is built here rather than at module scope: an aliased
        self-join resolves the relationship eagerly, and adapters are imported
        early enough that doing so at import time would configure the mappers
        before every model is registered.
        """
        parent = aliased(ChapterORM)
        stmt = (
            select(
                ChapterORM.id,
                ChapterORM.name,
                ChapterORM.chapter_number,
                parent.name.label("parent_name"),
                ChapterDigestORM.summary,
                ChapterDigestORM.keypoints,
                ChapterDigestORM.questions,
                ChapterDigestORM.generated_at,
            )
            .join(ChapterDigestORM, ChapterDigestORM.chapter_id == ChapterORM.id)
            .outerjoin(
                parent,
                # A parent in another book was never resolvable before either.
                (parent.id == ChapterORM.parent_id) & (parent.book_id == ChapterORM.book_id),
            )
            .where(ChapterORM.book_id == book_id)
            # Matches the chapter finder this view used to call, dialect-default
            # null ordering included.
            .order_by(ChapterORM.chapter_number)
        )
        rows = (await self.db.execute(stmt)).all()
        return tuple(
            EreaderChapterDigestView(
                chapter_id=row.id,
                chapter_name=row.name,
                chapter_number=row.chapter_number,
                parent_chapter_name=row.parent_name,
                summary=row.summary,
                keypoints=tuple(row.keypoints),
                questions=tuple(question["question"] for question in row.questions),
                generated_at=row.generated_at,
            )
            for row in rows
        )
