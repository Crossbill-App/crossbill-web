"""Turns search hits into renderable items by reading the source modules' ORM.

This is the read-side twin of ``ContentSource``: the same sanctioned reach
across module boundaries (ADR-0002), but for display fields rather than for the
text to embed. One select per content type, plus one for the note-to-book links,
so a page costs a fixed number of statements regardless of the limit.

Each method drops hits it cannot resolve. That is not a safety net over the
cascade anchors -- it is what makes "deleted content never surfaces" true
(ADR-0002's consistency model, rule 2), and it carries real weight for a
soft-deleted highlight, whose embedding survives until the next backfill sweep
because no foreign key can see an UPDATE of ``deleted_at``.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.queries.content_search import (
    BookRef,
    DigestSearchView,
    HighlightSearchView,
    NoteSearchView,
)
from src.application.semantic.queries.semantic_search import SemanticSearchHit
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.associations import note_books
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.chapter_digest_model import ChapterDigest as ChapterDigestORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM


def _scores(hits: Sequence[SemanticSearchHit]) -> dict[int, float]:
    """Map content id to score, preserving the ranking order of ``hits``.

    One entry per content id, never a collision: every scan is single-type and
    ``uq_embeddings_content`` makes ``(content_type, content_id)`` unique.
    """
    return {hit.content_id: hit.score for hit in hits}


class SearchHydrationQuery:
    """Resolves search hits into the items each content type's list renders."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def highlights(
        self, hits: Sequence[SemanticSearchHit], user_id: int
    ) -> tuple[HighlightSearchView, ...]:
        """Resolve highlight hits, dropping any that are gone or soft-deleted."""
        scores = _scores(hits)
        if not scores:
            return ()
        stmt = (
            select(
                HighlightORM.id,
                HighlightORM.book_id,
                BookORM.title.label("book_title"),
                HighlightORM.chapter_id,
                ChapterORM.name.label("chapter_name"),
                ChapterORM.chapter_number,
                HighlightORM.text,
                HighlightORM.page,
                HighlightORM.datetime,
            )
            .join(BookORM, HighlightORM.book_id == BookORM.id)
            .outerjoin(ChapterORM, HighlightORM.chapter_id == ChapterORM.id)
            .where(
                HighlightORM.id.in_(list(scores)),
                HighlightORM.user_id == user_id,
                HighlightORM.deleted_at.is_(None),
            )
        )
        found = {row.id: row for row in (await self.db.execute(stmt)).all()}
        return tuple(
            HighlightSearchView(
                score=score,
                id=row.id,
                book_id=row.book_id,
                book_title=row.book_title,
                chapter_id=row.chapter_id,
                chapter_name=row.chapter_name,
                chapter_number=row.chapter_number,
                text=row.text,
                page=row.page,
                datetime=row.datetime,
            )
            for content_id, score in scores.items()
            if (row := found.get(content_id)) is not None
        )

    async def notes(
        self, hits: Sequence[SemanticSearchHit], user_id: int
    ) -> tuple[NoteSearchView, ...]:
        """Resolve note hits together with the books each links to."""
        scores = _scores(hits)
        if not scores:
            return ()
        stmt = select(NoteORM.id, NoteORM.title, NoteORM.body, NoteORM.kind).where(
            NoteORM.id.in_(list(scores)), NoteORM.user_id == user_id
        )
        found = {row.id: row for row in (await self.db.execute(stmt)).all()}
        links = await self._note_books(list(found), user_id)
        return tuple(
            NoteSearchView(
                score=score,
                id=row.id,
                books=links.get(row.id, ()),
                title=row.title,
                body=row.body,
                kind=row.kind,
            )
            for content_id, score in scores.items()
            if (row := found.get(content_id)) is not None
        )

    async def digests(
        self, hits: Sequence[SemanticSearchHit], user_id: int
    ) -> tuple[DigestSearchView, ...]:
        """Resolve digest hits, carrying their chapter and book context.

        A digest has no ``user_id`` of its own, so ownership is enforced on the
        book the chapter belongs to -- the same join the scope query uses.
        """
        scores = _scores(hits)
        if not scores:
            return ()
        stmt = (
            select(
                ChapterDigestORM.id,
                ChapterDigestORM.summary,
                ChapterDigestORM.keypoints,
                ChapterORM.id.label("chapter_id"),
                ChapterORM.name.label("chapter_name"),
                ChapterORM.chapter_number,
                BookORM.id.label("book_id"),
                BookORM.title.label("book_title"),
            )
            .join(ChapterORM, ChapterDigestORM.chapter_id == ChapterORM.id)
            .join(BookORM, ChapterORM.book_id == BookORM.id)
            .where(ChapterDigestORM.id.in_(list(scores)), BookORM.user_id == user_id)
        )
        found = {row.id: row for row in (await self.db.execute(stmt)).all()}
        return tuple(
            DigestSearchView(
                score=score,
                id=row.id,
                book_id=row.book_id,
                book_title=row.book_title,
                chapter_id=row.chapter_id,
                chapter_name=row.chapter_name,
                chapter_number=row.chapter_number,
                summary=row.summary,
                keypoints=tuple(row.keypoints),
            )
            for content_id, score in scores.items()
            if (row := found.get(content_id)) is not None
        )

    async def _note_books(
        self, note_ids: list[int], user_id: int
    ) -> dict[int, tuple[BookRef, ...]]:
        """Group every note's linked books in one pass, rather than a query per note.

        ``note_ids`` is already restricted to the caller's own notes, but this
        re-asserts ownership on the book itself rather than trusting that --
        every other read in this module does the same.
        """
        if not note_ids:
            return {}
        stmt = (
            select(note_books.c.note_id, BookORM.id, BookORM.title)
            .join(BookORM, note_books.c.book_id == BookORM.id)
            .where(note_books.c.note_id.in_(note_ids), BookORM.user_id == user_id)
            .order_by(BookORM.id)
        )
        grouped: dict[int, list[BookRef]] = {}
        for note_id, book_id, title in (await self.db.execute(stmt)).all():
            grouped.setdefault(note_id, []).append(BookRef(id=book_id, title=title))
        return {note_id: tuple(refs) for note_id, refs in grouped.items()}
