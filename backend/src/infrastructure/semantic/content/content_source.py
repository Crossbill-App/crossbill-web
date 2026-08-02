"""Cross-module resolver of embeddable text and the reconciliation query.

This is the one sanctioned place where the ``semantic`` context reads other
modules' ORM directly (ADR-0002): it turns a ``(ContentType, content_id)`` key
into the text to embed, and enumerates the units whose stored embedding is
missing or model-stale so the backfill can re-embed exactly those.
"""

import hashlib

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import EmbeddableContent, WorkItem
from src.config import Settings
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.associations import note_books
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.chapter_digest_model import ChapterDigest as ChapterDigestORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM


def _note_text(title: str, body: str) -> str:
    return f"{title}\n\n{body}" if body else title


def _digest_text(summary: str, keypoints: list[str]) -> str:
    joined = "\n".join(keypoints)
    return f"{summary}\n\n{joined}" if joined else summary


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
        if content_type == ContentType.NOTE:
            return await self._note(content_id)
        if content_type == ContentType.HIGHLIGHT:
            return await self._highlight(content_id)
        return await self._digest(content_id)

    async def iter_work_items(self, user_id: int, book_id: int | None) -> list[WorkItem]:
        items: list[WorkItem] = []
        items.extend(await self._pending(self._note_scope(user_id, book_id), ContentType.NOTE))
        items.extend(
            await self._pending(self._highlight_scope(user_id, book_id), ContentType.HIGHLIGHT)
        )
        items.extend(await self._pending(self._digest_scope(user_id, book_id), ContentType.DIGEST))
        return items

    async def _note(self, content_id: int) -> EmbeddableContent | None:
        note = (
            await self.db.execute(select(NoteORM).where(NoteORM.id == content_id))
        ).scalar_one_or_none()
        if note is None:
            return None
        linked = (
            (
                await self.db.execute(
                    select(note_books.c.book_id).where(note_books.c.note_id == content_id)
                )
            )
            .scalars()
            .all()
        )
        text = _note_text(note.title, note.body)
        return EmbeddableContent(
            content_type=ContentType.NOTE,
            content_id=content_id,
            user_id=note.user_id,
            book_id=linked[0] if len(linked) == 1 else None,
            text=text,
            content_hash=_content_hash(text),
        )

    async def _highlight(self, content_id: int) -> EmbeddableContent | None:
        highlight = (
            await self.db.execute(
                select(HighlightORM).where(
                    HighlightORM.id == content_id,
                    HighlightORM.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if highlight is None:
            return None
        return EmbeddableContent(
            content_type=ContentType.HIGHLIGHT,
            content_id=content_id,
            user_id=highlight.user_id,
            book_id=highlight.book_id,
            text=highlight.text,
            content_hash=_content_hash(highlight.text),
        )

    async def _digest(self, content_id: int) -> EmbeddableContent | None:
        row = (
            await self.db.execute(
                select(ChapterDigestORM, ChapterORM.book_id, BookORM.user_id)
                .join(ChapterORM, ChapterDigestORM.chapter_id == ChapterORM.id)
                .join(BookORM, ChapterORM.book_id == BookORM.id)
                .where(ChapterDigestORM.id == content_id)
            )
        ).one_or_none()
        if row is None:
            return None
        digest, book_id, user_id = row
        text = _digest_text(digest.summary, digest.keypoints)
        return EmbeddableContent(
            content_type=ContentType.DIGEST,
            content_id=content_id,
            user_id=user_id,
            book_id=book_id,
            text=text,
            content_hash=_content_hash(text),
        )

    def _note_scope(self, user_id: int, book_id: int | None) -> Select[tuple[int]]:
        stmt = select(NoteORM.id).where(NoteORM.user_id == user_id)
        if book_id is not None:
            stmt = stmt.where(
                NoteORM.id.in_(select(note_books.c.note_id).where(note_books.c.book_id == book_id))
            )
        return self._only_pending(stmt, NoteORM.id, ContentType.NOTE)

    def _highlight_scope(self, user_id: int, book_id: int | None) -> Select[tuple[int]]:
        stmt = select(HighlightORM.id).where(
            HighlightORM.user_id == user_id,
            HighlightORM.deleted_at.is_(None),
        )
        if book_id is not None:
            stmt = stmt.where(HighlightORM.book_id == book_id)
        return self._only_pending(stmt, HighlightORM.id, ContentType.HIGHLIGHT)

    def _digest_scope(self, user_id: int, book_id: int | None) -> Select[tuple[int]]:
        stmt = (
            select(ChapterDigestORM.id)
            .join(ChapterORM, ChapterDigestORM.chapter_id == ChapterORM.id)
            .join(BookORM, ChapterORM.book_id == BookORM.id)
            .where(BookORM.user_id == user_id)
        )
        if book_id is not None:
            stmt = stmt.where(BookORM.id == book_id)
        return self._only_pending(stmt, ChapterDigestORM.id, ContentType.DIGEST)

    def _only_pending(
        self, stmt: Select[tuple[int]], id_column: object, content_type: ContentType
    ) -> Select[tuple[int]]:
        return stmt.outerjoin(
            EmbeddingORM,
            (EmbeddingORM.content_type == content_type.value)
            & (EmbeddingORM.content_id == id_column),
        ).where(
            or_(
                EmbeddingORM.id.is_(None),
                EmbeddingORM.model_name != self._settings.EMBEDDING_MODEL_NAME,
                EmbeddingORM.model_version != self._settings.EMBEDDING_MODEL_VERSION,
            )
        )

    async def _pending(self, stmt: Select[tuple[int]], content_type: ContentType) -> list[WorkItem]:
        ids = (await self.db.execute(stmt)).scalars().all()
        return [WorkItem(content_type=content_type, content_id=row_id) for row_id in ids]
