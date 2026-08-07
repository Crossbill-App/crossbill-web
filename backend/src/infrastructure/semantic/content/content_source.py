"""Cross-module resolver of embeddable text and the reconciliation query.

This is the one sanctioned place where the ``semantic`` context reads other
modules' ORM directly (ADR-0002): it turns a ``(ContentType, content_id)`` key
into the text to embed, and enumerates the units the backfill must act on --
those whose stored embedding is missing, model-stale or content-stale, plus
those whose embedding outlived its source row.
"""

import hashlib
from collections.abc import Callable
from typing import Any

from sqlalchemy import Row, Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.application.semantic.idempotency import is_current
from src.application.semantic.protocols.content_source import EmbeddableContent, PendingUnit
from src.application.semantic.protocols.embedding_repository import EmbeddingState
from src.config import Settings
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.associations import note_books
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.chapter_digest_model import ChapterDigest as ChapterDigestORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM

#: Longest text sent to the embedding model, in characters.
#:
#: ADR-0002 asserts every unit fits ``bge-m3``'s 8K-token context and does not
#: chunk. Nothing enforced that: ``notes.body`` is an unbounded ``Text`` column
#: with no length validation on the way in, so a long enough note is whatever
#: the provider decides -- Ollama truncates quietly, OpenRouter is likelier to
#: reject the request. A rejection is the expensive outcome, because a unit that
#: cannot be embedded stays stale forever: every backfill picks it up again and
#: spends a job and its retries on it.
#:
#: 8000 characters is deliberately conservative. The reading data is mixed
#: Finnish/English, and Finnish tokenises far worse than English, so even at a
#: pessimistic 2 characters per token this stays under half the context.
#:
#: The tail of an over-long unit is simply not indexed. That follows from the
#: ADR's "one vector per unit" -- chunking is what would index it, and that was
#: explicitly not adopted.
MAX_EMBEDDABLE_CHARS = 8000


def _truncate(text: str) -> str:
    return text[:MAX_EMBEDDABLE_CHARS]


def _note_text(title: str, body: str) -> str:
    return _truncate(f"{title}\n\n{body}" if body else title)


def _highlight_text(text: str) -> str:
    """Exists so the highlight path truncates in one place, like the other two.

    Both the reconciliation scan and ``get_embeddable_many`` have to arrive at
    the same string: they hash independently, and a unit whose two hashes differ
    is stale on every pass no matter how often it is embedded.
    """
    return _truncate(text)


def _digest_text(summary: str, keypoints: list[str]) -> str:
    joined = "\n".join(keypoints)
    return _truncate(f"{summary}\n\n{joined}" if joined else summary)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ContentSource:
    """Reads source-module ORM to resolve embeddable text and pending work."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self._settings = settings

    async def get_embeddable(
        self, content_type: ContentType, content_id: int
    ) -> EmbeddableContent | None:
        """Resolve one unit. A special case of the bulk path, so the two cannot drift."""
        found = await self.get_embeddable_many(content_type, [content_id])
        return found.get(content_id)

    async def get_embeddable_many(
        self, content_type: ContentType, content_ids: list[int]
    ) -> dict[int, EmbeddableContent]:
        """Resolve many units of one type, keyed by id; missing ids are simply absent."""
        if not content_ids:
            return {}
        if content_type == ContentType.NOTE:
            return await self._notes(content_ids)
        if content_type == ContentType.HIGHLIGHT:
            return await self._highlights(content_ids)
        return await self._digests(content_ids)

    async def find_units_needing_embedding(
        self, user_id: int, book_id: int | None
    ) -> list[PendingUnit]:
        items: list[PendingUnit] = []
        items.extend(
            await self._pending(
                self._note_scope(user_id, book_id),
                ContentType.NOTE,
                lambda row: _note_text(row.title, row.body),
            )
        )
        items.extend(
            await self._pending(
                self._highlight_scope(user_id, book_id),
                ContentType.HIGHLIGHT,
                lambda row: _highlight_text(row.text),
            )
        )
        items.extend(
            await self._pending(
                self._digest_scope(user_id, book_id),
                ContentType.DIGEST,
                lambda row: _digest_text(row.summary, row.keypoints),
            )
        )
        items.extend(await self._orphans(user_id, book_id))
        return items

    async def _notes(self, content_ids: list[int]) -> dict[int, EmbeddableContent]:
        # Columns, not entities: selecting the mapped class drags in its
        # selectin-loaded relationships, costing an extra query per relationship
        # for data hydration never reads.
        notes = (
            await self.db.execute(
                select(NoteORM.id, NoteORM.user_id, NoteORM.title, NoteORM.body).where(
                    NoteORM.id.in_(content_ids)
                )
            )
        ).all()
        if not notes:
            return {}

        # One pass for every note's book links, grouped in memory, rather than a
        # follow-up query per note.
        links: dict[int, list[int]] = {}
        rows = await self.db.execute(
            select(note_books.c.note_id, note_books.c.book_id).where(
                note_books.c.note_id.in_(content_ids)
            )
        )
        for note_id, book_id in rows:
            links.setdefault(note_id, []).append(book_id)

        resolved: dict[int, EmbeddableContent] = {}
        for note in notes:
            linked = links.get(note.id, [])
            text = _note_text(note.title, note.body)
            resolved[note.id] = EmbeddableContent(
                content_type=ContentType.NOTE,
                content_id=note.id,
                user_id=note.user_id,
                # A note linked to two books gets NULL here: no single value is
                # correct, and picking one would make `?book_id=` depend on link
                # order. Search no longer suffers for it -- the note scan filters
                # through note_books (``SemanticSearchQuery._book_filter``) rather
                # than this column. The column stays NULL, so anything else that
                # scopes on it still cannot see such a note.
                # Only a note linked to exactly one book gets a scope. A note
                # spanning two books has no single correct value, and picking one
                # arbitrarily would make `?book_id=` results depend on link order
                # -- so it stays NULL and such notes surface in unscoped search
                # only. Backfill still embeds them under a book's scope; they just
                # aren't filterable by it.
                book_id=linked[0] if len(linked) == 1 else None,
                text=text,
                content_hash=_content_hash(text),
            )
        return resolved

    async def _highlights(self, content_ids: list[int]) -> dict[int, EmbeddableContent]:
        highlights = (
            await self.db.execute(
                select(
                    HighlightORM.id,
                    HighlightORM.user_id,
                    HighlightORM.book_id,
                    HighlightORM.text,
                ).where(
                    HighlightORM.id.in_(content_ids),
                    HighlightORM.deleted_at.is_(None),
                )
            )
        ).all()
        resolved: dict[int, EmbeddableContent] = {}
        for highlight in highlights:
            text = _highlight_text(highlight.text)
            resolved[highlight.id] = EmbeddableContent(
                content_type=ContentType.HIGHLIGHT,
                content_id=highlight.id,
                user_id=highlight.user_id,
                book_id=highlight.book_id,
                text=text,
                content_hash=_content_hash(text),
            )
        return resolved

    async def _digests(self, content_ids: list[int]) -> dict[int, EmbeddableContent]:
        rows = (
            await self.db.execute(
                select(
                    ChapterDigestORM.id,
                    ChapterDigestORM.summary,
                    ChapterDigestORM.keypoints,
                    ChapterORM.book_id,
                    BookORM.user_id,
                )
                .join(ChapterORM, ChapterDigestORM.chapter_id == ChapterORM.id)
                .join(BookORM, ChapterORM.book_id == BookORM.id)
                .where(ChapterDigestORM.id.in_(content_ids))
            )
        ).all()

        resolved: dict[int, EmbeddableContent] = {}
        for digest_id, summary, keypoints, book_id, user_id in rows:
            text = _digest_text(summary, keypoints)
            resolved[digest_id] = EmbeddableContent(
                content_type=ContentType.DIGEST,
                content_id=digest_id,
                user_id=user_id,
                book_id=book_id,
                text=text,
                content_hash=_content_hash(text),
            )
        return resolved

    def _note_scope(self, user_id: int, book_id: int | None) -> Select[Any]:
        stmt = select(NoteORM.id.label("content_id"), NoteORM.title, NoteORM.body).where(
            NoteORM.user_id == user_id
        )
        if book_id is not None:
            stmt = stmt.where(
                NoteORM.id.in_(select(note_books.c.note_id).where(note_books.c.book_id == book_id))
            )
        return self._with_embedding_state(stmt, NoteORM.id, ContentType.NOTE)

    def _highlight_scope(self, user_id: int, book_id: int | None) -> Select[Any]:
        stmt = select(HighlightORM.id.label("content_id"), HighlightORM.text).where(
            HighlightORM.user_id == user_id,
            HighlightORM.deleted_at.is_(None),
        )
        if book_id is not None:
            stmt = stmt.where(HighlightORM.book_id == book_id)
        return self._with_embedding_state(stmt, HighlightORM.id, ContentType.HIGHLIGHT)

    def _digest_scope(self, user_id: int, book_id: int | None) -> Select[Any]:
        stmt = (
            select(
                ChapterDigestORM.id.label("content_id"),
                ChapterDigestORM.summary,
                ChapterDigestORM.keypoints,
            )
            .join(ChapterORM, ChapterDigestORM.chapter_id == ChapterORM.id)
            .join(BookORM, ChapterORM.book_id == BookORM.id)
            .where(BookORM.user_id == user_id)
        )
        if book_id is not None:
            stmt = stmt.where(BookORM.id == book_id)
        return self._with_embedding_state(stmt, ChapterDigestORM.id, ContentType.DIGEST)

    def _with_embedding_state(
        self, stmt: Select[Any], id_column: object, content_type: ContentType
    ) -> Select[Any]:
        """Outer-join the stored embedding's idempotency state onto a scope query.

        The staleness decision itself happens in Python, not SQL: ``content_hash``
        is a SHA-256 over text assembled in application code, and there is no
        portable way to recompute it in both Postgres and SQLite. So this selects
        the state and lets ``_is_stale`` compare it.
        """
        return stmt.add_columns(
            EmbeddingORM.id.label("embedding_id"),
            EmbeddingORM.model_name.label("stored_model_name"),
            EmbeddingORM.model_version.label("stored_model_version"),
            EmbeddingORM.content_hash.label("stored_content_hash"),
        ).outerjoin(
            EmbeddingORM,
            (EmbeddingORM.content_type == content_type.value)
            & (EmbeddingORM.content_id == id_column),
        )

    def _is_stale(self, row: Row[Any], text: str) -> bool:
        """The ADR-0002 spine: missing, model-drifted, or content-drifted.

        Scope is deliberately not compared: a note whose book links changed with
        its text untouched would keep a stale ``book_id`` forever. Unreachable
        today only because ``UpdateNoteUseCase`` passes the note's existing
        ``book_ids`` straight through; revisit when book links become editable.
        """
        if row.embedding_id is None:
            return True
        stored = EmbeddingState(
            content_hash=row.stored_content_hash,
            model_name=row.stored_model_name,
            model_version=row.stored_model_version,
        )
        return not is_current(stored, _content_hash(text), self._settings)

    async def _pending(
        self,
        stmt: Select[Any],
        content_type: ContentType,
        to_text: Callable[[Row[Any]], str],
    ) -> list[PendingUnit]:
        rows = (await self.db.execute(stmt)).all()
        return [
            PendingUnit(content_type=content_type, content_id=row.content_id)
            for row in rows
            if self._is_stale(row, to_text(row))
        ]

    async def _orphans(self, user_id: int, book_id: int | None) -> list[PendingUnit]:
        """Embeddings left behind by a soft-deleted highlight.

        Only a highlight can strand one. Notes and digests are hard-deleted
        only, and their typed FK anchors cascade the embedding away in either
        race ordering: the FK check takes ``FOR KEY SHARE`` on the referenced
        row, so a concurrent DELETE either waits for the insert and then
        cascades it, or wins and the insert fails on the FK -- leaving the retry
        to resolve ``None`` and delete. Sweeping them too meant an unindexed
        anti-join across all of the user's notes and digests, per backfill,
        hunting rows that cannot exist.

        A soft delete is an UPDATE, which no foreign key can see, so this
        remains the backstop for a highlight: for the window where a job in
        flight across ``embed()`` re-inserts a row for content just deleted, and
        for a cleanup that failed outright.

        Handing these back as pending units is enough to prune them: the job's
        ``get_embeddable`` returns ``None`` and the existing "source missing ->
        delete_for" branch removes the row. No separate delete path needed.
        """
        # Positive form on the anchor column, which has a partial index --
        # cheaper than an anti-join against every live highlight.
        soft_deleted = select(HighlightORM.id).where(HighlightORM.deleted_at.is_not(None))
        stmt = select(EmbeddingORM.content_id).where(
            EmbeddingORM.user_id == user_id,
            EmbeddingORM.highlight_id.in_(soft_deleted),
        )
        if book_id is not None:
            stmt = stmt.where(EmbeddingORM.book_id == book_id)
        ids = (await self.db.execute(stmt)).scalars().all()
        return [
            PendingUnit(content_type=ContentType.HIGHLIGHT, content_id=content_id)
            for content_id in ids
        ]
