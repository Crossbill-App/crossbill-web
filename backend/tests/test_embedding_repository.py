"""Tests for EmbeddingRepository (runs against in-memory SQLite)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_repository import EmbeddingWrite
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM
from src.infrastructure.semantic.repositories.embedding_repository import EmbeddingRepository
from src.models import Book, Chapter, ChapterDigest, Highlight, Note

VECTOR = [0.1, 0.2, 0.3]
OTHER_VECTOR = [0.9, 0.8, 0.7]


def _write(
    content_type: ContentType,
    content_id: int,
    *,
    book_id: int | None = 7,
    embedding: list[float] = VECTOR,
    model_version: str = "1",
    content_hash: str = "a" * 64,
) -> EmbeddingWrite:
    return EmbeddingWrite(
        content_type=content_type,
        content_id=content_id,
        user_id=1,
        book_id=book_id,
        embedding=embedding,
        model_name="bge-m3",
        model_version=model_version,
        content_hash=content_hash,
    )


@pytest.fixture(autouse=True)
async def _referenced_content(db_session: AsyncSession) -> None:  # pyright: ignore[reportUnusedFunction]
    """Every id these writes use is a real FK now, so the source rows must exist.

    That is the point of the cascade anchors: an embedding cannot reference
    content that does not exist.
    """
    db_session.add_all(
        [
            Book(id=1, user_id=1, title="Book one"),
            Book(id=7, user_id=1, title="Book seven"),
            Note(id=11, user_id=1, title="Note eleven", body="b"),
            Note(id=42, user_id=1, title="Note forty-two", body="b"),
            Highlight(
                id=5,
                user_id=1,
                book_id=7,
                text="highlight five",
                datetime="2024-01-15 14:30:22",
                content_hash="f" * 64,
            ),
            Chapter(id=3, book_id=7, name="Chapter three"),
        ]
    )
    await db_session.commit()
    db_session.add(
        ChapterDigest(
            id=3,
            chapter_id=3,
            summary="s",
            keypoints=[],
            questions=[],
            generated_at=datetime.now(UTC),
            ai_model="m",
        )
    )
    await db_session.commit()


@pytest.fixture
def embedding_repository(db_session: AsyncSession) -> EmbeddingRepository:
    return EmbeddingRepository(db_session)


class TestUpsert:
    async def test_insert_creates_row(
        self, embedding_repository: EmbeddingRepository, db_session: AsyncSession
    ) -> None:
        await embedding_repository.upsert(_write(ContentType.NOTE, 42))

        result = await db_session.execute(select(EmbeddingORM).where(EmbeddingORM.content_id == 42))
        row = result.scalar_one()
        assert row.content_type == "note"
        assert row.book_id == 7
        assert row.embedding == VECTOR
        assert row.content_hash == "a" * 64

    async def test_second_upsert_replaces_in_place(
        self, embedding_repository: EmbeddingRepository, db_session: AsyncSession
    ) -> None:
        for embedding, content_hash, book_id in (
            (VECTOR, "a" * 64, 7),
            (OTHER_VECTOR, "b" * 64, None),
        ):
            await embedding_repository.upsert(
                _write(
                    ContentType.HIGHLIGHT,
                    5,
                    book_id=book_id,
                    embedding=embedding,
                    model_version="2",
                    content_hash=content_hash,
                )
            )

        result = await db_session.execute(
            select(EmbeddingORM).where(
                EmbeddingORM.content_type == "highlight", EmbeddingORM.content_id == 5
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].embedding == OTHER_VECTOR
        assert rows[0].book_id is None
        assert rows[0].content_hash == "b" * 64
        assert rows[0].model_version == "2"


class TestGetState:
    async def test_returns_none_when_absent(
        self, embedding_repository: EmbeddingRepository
    ) -> None:
        assert await embedding_repository.get_state(ContentType.DIGEST, 999) is None

    async def test_returns_stored_idempotency_state(
        self, embedding_repository: EmbeddingRepository
    ) -> None:
        await embedding_repository.upsert(
            _write(ContentType.DIGEST, 3, book_id=1, content_hash="c" * 64)
        )

        state = await embedding_repository.get_state(ContentType.DIGEST, 3)
        assert state is not None
        assert state.content_hash == "c" * 64
        assert state.model_name == "bge-m3"
        assert state.model_version == "1"


class TestDeleteFor:
    async def test_removes_matching_row(self, embedding_repository: EmbeddingRepository) -> None:
        await embedding_repository.upsert(
            _write(ContentType.NOTE, 11, book_id=None, content_hash="d" * 64)
        )

        await embedding_repository.delete_for(ContentType.NOTE, [11])

        assert await embedding_repository.get_state(ContentType.NOTE, 11) is None

    async def test_delete_absent_is_noop(self, embedding_repository: EmbeddingRepository) -> None:
        await embedding_repository.delete_for(ContentType.NOTE, [123])


class TestCascadeAnchors:
    async def test_upsert_sets_only_the_matching_anchor(
        self, embedding_repository: EmbeddingRepository, db_session: AsyncSession
    ) -> None:
        await embedding_repository.upsert(_write(ContentType.NOTE, 42))

        row = (
            await db_session.execute(select(EmbeddingORM).where(EmbeddingORM.content_id == 42))
        ).scalar_one()
        assert row.note_id == 42
        assert row.highlight_id is None
        assert row.digest_id is None

    async def test_deleting_the_note_cascades_the_embedding(
        self, embedding_repository: EmbeddingRepository, db_session: AsyncSession
    ) -> None:
        """No FK on the polymorphic content_id; the note_id anchor is what cascades."""
        await embedding_repository.upsert(_write(ContentType.NOTE, 42))

        note = (await db_session.execute(select(Note).where(Note.id == 42))).scalar_one()
        await db_session.delete(note)
        await db_session.commit()

        assert await embedding_repository.get_state(ContentType.NOTE, 42) is None

    async def test_deleting_the_digest_cascades_the_embedding(
        self, embedding_repository: EmbeddingRepository, db_session: AsyncSession
    ) -> None:
        await embedding_repository.upsert(_write(ContentType.DIGEST, 3, book_id=7))

        digest = (
            await db_session.execute(select(ChapterDigest).where(ChapterDigest.id == 3))
        ).scalar_one()
        await db_session.delete(digest)
        await db_session.commit()

        assert await embedding_repository.get_state(ContentType.DIGEST, 3) is None

    async def test_deleting_the_book_clears_scope_but_keeps_the_note(
        self, embedding_repository: EmbeddingRepository, db_session: AsyncSession
    ) -> None:
        """book_id is SET NULL: a note outlives its book, so its embedding must too."""
        await embedding_repository.upsert(_write(ContentType.NOTE, 42, book_id=7))

        book = (await db_session.execute(select(Book).where(Book.id == 7))).scalar_one()
        await db_session.delete(book)
        await db_session.commit()

        row = (
            await db_session.execute(select(EmbeddingORM).where(EmbeddingORM.content_id == 42))
        ).scalar_one_or_none()
        assert row is not None, "the note is still alive, so its embedding must survive"
        assert row.book_id is None, "but the dead book's scope is cleared"

    async def test_anchor_cannot_drift_from_content_id(self, db_session: AsyncSession) -> None:
        """The CHECK is what makes the duplicated id safe."""
        db_session.add(
            EmbeddingORM(
                user_id=1,
                content_type="note",
                content_id=42,
                note_id=11,  # points at a different note than content_id
                book_id=None,
                embedding=VECTOR,
                model_name="bge-m3",
                model_version="1",
                content_hash="a" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_row_with_no_anchor_at_all_is_rejected(self, db_session: AsyncSession) -> None:
        """The case the CHECK used to wave through, and the worst one.

        Comparing a NULL anchor to content_id yields NULL, the disjunction yields
        NULL, and SQL satisfies any CHECK that is not false -- so the row the
        anchors exist to prevent was the one row they let past. Nothing cascades
        it and the orphan sweep, which reads the anchor, cannot see it either.
        """
        db_session.add(
            EmbeddingORM(
                user_id=1,
                content_type="highlight",
                content_id=42,
                book_id=None,
                embedding=VECTOR,
                model_name="bge-m3",
                model_version="1",
                content_hash="a" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()
