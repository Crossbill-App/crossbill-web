"""Query adapter for the note views.

Rows map straight to view DTOs: no aggregate is loaded, so a note's links no
longer drag whole ``Book``, ``Chapter``, ``Highlight`` and ``Tag`` rows into
memory just to yield their ids. The link ids come from the association tables
directly; the entities the view renders are fetched separately, because the two
answer different questions -- ``highlight_ids`` is what the note points at,
while ``highlights`` is what this user is allowed to see.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime as dt
from typing import TypeVar

from sqlalchemy import ColumnElement, Select, Table, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.application.notes.queries.note_with_links import (
    LinkedChapterView,
    LinkedHighlightView,
    LinkedTagView,
    NoteFlashcardView,
    NoteWithLinksView,
)
from src.domain.common.value_objects.ids import (
    BookId,
    ChapterId,
    HighlightId,
    NoteId,
    TagId,
    UserId,
)
from src.domain.notes.entities.note import NoteKind
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.associations import (
    note_books,
    note_chapters,
    note_highlights,
    note_tags,
)
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM

_NoteRow = tuple[int, int, str, str, str | None, dt, dt]
_LinkIds = dict[int, tuple[int, ...]]
TLink = TypeVar("TLink", LinkedChapterView, LinkedHighlightView, LinkedTagView)


def _select_notes() -> Select[_NoteRow]:
    """Select the note's own columns; links are resolved separately."""
    return select(
        NoteORM.id,
        NoteORM.user_id,
        NoteORM.title,
        NoteORM.body,
        NoteORM.kind,
        NoteORM.created_at,
        NoteORM.updated_at,
    )


class NoteQuery:
    """Serves the note read model from purpose-built selects."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_note(self, note_id: NoteId, user_id: UserId) -> NoteWithLinksView | None:
        """Return one of the user's notes, or ``None`` when they have no such note."""
        result = await self.db.execute(
            _select_notes().where(
                NoteORM.id == note_id.value,
                NoteORM.user_id == user_id.value,
            )
        )
        row = result.tuples().first()
        if row is None:
            return None

        views = await self._build_views([row], user_id)
        return views[0]

    async def list_for_book(
        self,
        book_id: BookId,
        user_id: UserId,
        kind: NoteKind | None = None,
        chapter_id: ChapterId | None = None,
        highlight_id: HighlightId | None = None,
        tag_id: TagId | None = None,
    ) -> tuple[NoteWithLinksView, ...]:
        """Return the user's notes for a book, ordered by title."""
        stmt = (
            _select_notes()
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
        return await self._build_views(result.tuples().all(), user_id)

    async def _build_views(
        self, rows: Sequence[_NoteRow], user_id: UserId
    ) -> tuple[NoteWithLinksView, ...]:
        """Resolve the links of every note row and assemble the view DTOs."""
        if not rows:
            return ()

        note_ids = [row[0] for row in rows]
        flashcards_by_note = await self._fetch_flashcards(note_ids, user_id)
        book_ids = await self._fetch_link_ids(note_books, note_books.c.book_id, note_ids)
        chapter_ids = await self._fetch_link_ids(
            note_chapters, note_chapters.c.chapter_id, note_ids
        )
        highlight_ids = await self._fetch_link_ids(
            note_highlights, note_highlights.c.highlight_id, note_ids
        )
        tag_ids = await self._fetch_link_ids(note_tags, note_tags.c.tag_id, note_ids)

        chapters = await self._fetch_chapters(_union(chapter_ids), user_id)
        highlights = await self._fetch_highlights(_union(highlight_ids), user_id)
        tags = await self._fetch_tags(_union(tag_ids), user_id)

        return tuple(
            NoteWithLinksView(
                id=note_id,
                user_id=row_user_id,
                title=title,
                body=body,
                kind=NoteKind(kind) if kind else None,
                book_ids=book_ids.get(note_id, ()),
                chapter_ids=chapter_ids.get(note_id, ()),
                highlight_ids=highlight_ids.get(note_id, ()),
                tag_ids=tag_ids.get(note_id, ()),
                chapters=_resolve(chapter_ids.get(note_id, ()), chapters),
                highlights=_resolve(highlight_ids.get(note_id, ()), highlights),
                tags=_resolve(tag_ids.get(note_id, ()), tags),
                flashcards=flashcards_by_note.get(note_id, ()),
                created_at=created_at,
                updated_at=updated_at,
            )
            for note_id, row_user_id, title, body, kind, created_at, updated_at in rows
        )

    async def _fetch_link_ids(
        self, table: Table, target: ColumnElement[int], note_ids: list[int]
    ) -> _LinkIds:
        """Read one association table into ``note id -> linked ids``.

        Ownership is deliberately not applied: these are the note's own link
        sets, which the API reports verbatim.
        """
        stmt = (
            select(table.c.note_id, target)
            .where(table.c.note_id.in_(note_ids))
            .order_by(table.c.note_id, target)
        )
        grouped: dict[int, list[int]] = defaultdict(list)
        for note_id, target_id in (await self.db.execute(stmt)).tuples().all():
            grouped[note_id].append(target_id)
        return {note_id: tuple(ids) for note_id, ids in grouped.items()}

    async def _fetch_chapters(
        self, chapter_ids: set[int], user_id: UserId
    ) -> dict[int, LinkedChapterView]:
        """Load the linked chapters the user owns, via their book."""
        if not chapter_ids:
            return {}
        stmt = (
            select(ChapterORM.id, ChapterORM.name)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(
                ChapterORM.id.in_(chapter_ids),
                BookORM.user_id == user_id.value,
            )
        )
        rows = (await self.db.execute(stmt)).tuples().all()
        return {row[0]: LinkedChapterView(id=row[0], name=row[1]) for row in rows}

    async def _fetch_highlights(
        self, highlight_ids: set[int], user_id: UserId
    ) -> dict[int, LinkedHighlightView]:
        """Load the linked highlights the user owns that are not soft-deleted."""
        if not highlight_ids:
            return {}
        stmt = select(HighlightORM.id, HighlightORM.text).where(
            HighlightORM.id.in_(highlight_ids),
            HighlightORM.user_id == user_id.value,
            HighlightORM.deleted_at.is_(None),
        )
        rows = (await self.db.execute(stmt)).tuples().all()
        return {row[0]: LinkedHighlightView(id=row[0], text=row[1]) for row in rows}

    async def _fetch_tags(self, tag_ids: set[int], user_id: UserId) -> dict[int, LinkedTagView]:
        """Load the linked tags the user owns.

        Fetched by id rather than by book: a tag attached to a note but to no
        highlight is still shown on the note.
        """
        if not tag_ids:
            return {}
        stmt = select(TagORM.id, TagORM.name).where(
            TagORM.id.in_(tag_ids),
            TagORM.user_id == user_id.value,
        )
        rows = (await self.db.execute(stmt)).tuples().all()
        return {row[0]: LinkedTagView(id=row[0], name=row[1]) for row in rows}

    async def _fetch_flashcards(
        self, note_ids: list[int], user_id: UserId
    ) -> dict[int, tuple[NoteFlashcardView, ...]]:
        """Load every note's flashcards in one pass, newest first within a note."""
        stmt = (
            select(
                FlashcardORM.id,
                FlashcardORM.user_id,
                FlashcardORM.book_id,
                FlashcardORM.highlight_id,
                FlashcardORM.chapter_id,
                FlashcardORM.note_id,
                FlashcardORM.question,
                FlashcardORM.answer,
            )
            .where(
                FlashcardORM.note_id.in_(note_ids),
                FlashcardORM.user_id == user_id.value,
            )
            .order_by(FlashcardORM.note_id, FlashcardORM.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).tuples().all()
        grouped: dict[int | None, list[NoteFlashcardView]] = defaultdict(list)
        for (
            card_id,
            card_user_id,
            book_id,
            highlight_id,
            chapter_id,
            card_note_id,
            question,
            answer,
        ) in rows:
            grouped[card_note_id].append(
                NoteFlashcardView(
                    id=card_id,
                    user_id=card_user_id,
                    book_id=book_id,
                    highlight_id=highlight_id,
                    chapter_id=chapter_id,
                    note_id=card_note_id,
                    question=question,
                    answer=answer,
                )
            )
        # ``note_id`` is nullable on the table -- book-level cards keep no note.
        return {note_id: tuple(cards) for note_id, cards in grouped.items() if note_id is not None}


def _union(link_ids: _LinkIds) -> set[int]:
    """Collect every linked id across the notes, for one bulk lookup per kind."""
    return {target_id for ids in link_ids.values() for target_id in ids}


def _resolve(ids: Iterable[int], by_id: dict[int, TLink]) -> tuple[TLink, ...]:
    """Render the links in the note's own order, dropping the invisible ones."""
    return tuple(by_id[target_id] for target_id in ids if target_id in by_id)
