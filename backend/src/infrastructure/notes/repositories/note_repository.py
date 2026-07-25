"""Repository for Note domain entities."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    HighlightId,
    TagId,
    UserId,
)
from src.domain.notes.entities.note import Note, NoteKind
from src.domain.notes.exceptions import NoteNotFoundError
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.mappers.note_mapper import NoteMapper
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM


class NoteRepository(BaseRepository[Note, NoteORM]):
    """Repository for Note domain entities.

    ``find_by_id`` and ``delete`` are inherited from :class:`BaseRepository`;
    ``save`` is overridden because a note also owns association collections.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.mapper = NoteMapper()
        super().__init__(db, NoteORM, self.mapper)

    async def find_by_book(
        self,
        book_id: BookId,
        user_id: UserId,
        kind: NoteKind | None = None,
        chapter_id: ChapterId | None = None,
        highlight_id: HighlightId | None = None,
        tag_id: TagId | None = None,
    ) -> list[Note]:
        stmt = (
            select(NoteORM)
            .where(
                NoteORM.user_id == user_id.value,
                NoteORM.books.any(BookORM.id == book_id.value),
            )
            .order_by(func.lower(NoteORM.title))
        )
        if kind is not None:
            stmt = stmt.where(NoteORM.kind == kind.value)
        if chapter_id is not None:
            stmt = stmt.where(NoteORM.chapters.any(ChapterORM.id == chapter_id.value))
        if highlight_id is not None:
            stmt = stmt.where(NoteORM.highlights.any(HighlightORM.id == highlight_id.value))
        if tag_id is not None:
            stmt = stmt.where(NoteORM.tags.any(TagORM.id == tag_id.value))
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()
        return [self.mapper.to_domain(orm) for orm in orm_models]

    async def save(self, note: Note) -> Note:
        if note.id.value == 0:
            orm_model = self.mapper.to_orm(note)
            await self._sync_links(orm_model, note)
            self.db.add(orm_model)
            await self.db.flush()
        else:
            orm_model = await self.db.get(NoteORM, note.id.value)
            if not orm_model:
                raise NoteNotFoundError(note.id.value)
            self.mapper.to_orm(note, orm_model)
            await self._sync_links(orm_model, note)
        note_id = orm_model.id
        await self.db.commit()

        # Re-select to get fresh timestamps and eagerly-loaded collections
        stmt = select(NoteORM).where(NoteORM.id == note_id)
        result = await self.db.execute(stmt)
        saved = result.scalar_one()
        return self.mapper.to_domain(saved)

    async def _sync_links(self, orm_model: NoteORM, note: Note) -> None:
        """Replace association collections with rows matching the note's link ids."""
        if note.book_ids:
            result = await self.db.execute(select(BookORM).where(BookORM.id.in_(note.book_ids)))
            orm_model.books = list(result.scalars().all())
        else:
            orm_model.books = []

        if note.chapter_ids:
            result = await self.db.execute(
                select(ChapterORM).where(ChapterORM.id.in_(note.chapter_ids))
            )
            orm_model.chapters = list(result.scalars().all())
        else:
            orm_model.chapters = []

        if note.highlight_ids:
            result = await self.db.execute(
                select(HighlightORM).where(HighlightORM.id.in_(note.highlight_ids))
            )
            orm_model.highlights = list(result.scalars().all())
        else:
            orm_model.highlights = []

        if note.tag_ids:
            result = await self.db.execute(select(TagORM).where(TagORM.id.in_(note.tag_ids)))
            orm_model.tags = list(result.scalars().all())
        else:
            orm_model.tags = []
