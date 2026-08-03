"""Tests for EmbeddingRepository (runs against in-memory SQLite)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_repository import EmbeddingWrite
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM
from src.infrastructure.semantic.repositories.embedding_repository import EmbeddingRepository
from src.models import Book

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
async def _referenced_books(db_session: AsyncSession) -> None:  # pyright: ignore[reportUnusedFunction]
    """embeddings.book_id is a real FK, so the books these writes point at must exist."""
    db_session.add_all(
        [
            Book(id=1, user_id=1, title="Book one"),
            Book(id=7, user_id=1, title="Book seven"),
        ]
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

        await embedding_repository.delete_for(ContentType.NOTE, 11)

        assert await embedding_repository.get_state(ContentType.NOTE, 11) is None

    async def test_delete_absent_is_noop(self, embedding_repository: EmbeddingRepository) -> None:
        await embedding_repository.delete_for(ContentType.NOTE, 123)
