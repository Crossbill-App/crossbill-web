"""Tests for the POST /semantic/backfill ingestion endpoint."""

import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.semantic.content_type import ContentType
from src.config import get_settings
from src.models import Book, Embedding, Highlight

ENABLED = "src.infrastructure.common.dependencies.is_embeddings_enabled"


@pytest.fixture
async def override_queue() -> AsyncGenerator[AsyncMock, None]:
    """Override the SAQ queue service (normally wired by the app lifespan)."""
    from src.core import container  # noqa: PLC0415

    fake = AsyncMock()
    fake.enqueue = AsyncMock(side_effect=lambda fn, **kw: f"saq:{kw['content_id']}")
    container.job_queue_service.override(fake)
    yield fake
    container.job_queue_service.reset_override()


class TestBackfillEndpoint:
    async def test_blocked_when_embeddings_disabled(
        self, client: AsyncClient, override_queue: AsyncMock
    ) -> None:
        with patch(ENABLED, return_value=False):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        override_queue.enqueue.assert_not_called()

    async def test_enqueues_a_batch_when_enabled(
        self,
        client: AsyncClient,
        override_queue: AsyncMock,
        test_book: Book,
        test_highlight: Highlight,
    ) -> None:
        with patch(ENABLED, return_value=True):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["batch_type"] == "content_embedding"
        assert data["total_jobs"] >= 1
        assert data["status"] == "pending"
        override_queue.enqueue.assert_awaited()

    async def test_returns_error_when_nothing_to_embed(
        self, client: AsyncClient, override_queue: AsyncMock, db_session: AsyncSession
    ) -> None:
        with patch(ENABLED, return_value=True):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code >= status.HTTP_400_BAD_REQUEST
        override_queue.enqueue.assert_not_called()


def _current_model() -> tuple[str, str]:
    """The model identity a freshly written embedding would carry in this env."""
    settings = get_settings()
    return settings.EMBEDDING_MODEL_NAME or "", settings.EMBEDDING_MODEL_VERSION


async def _add_highlight(
    db: AsyncSession, book: Book, text: str, *, deleted: bool = False
) -> Highlight:
    highlight = Highlight(
        user_id=book.user_id,
        book_id=book.id,
        text=text,
        datetime="2024-01-15 14:30:22",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(highlight)
    await db.commit()
    await db.refresh(highlight)
    return highlight


async def _index(db: AsyncSession, book: Book, highlight: Highlight, hashed_text: str) -> None:
    """Index a highlight as if `hashed_text` were its content, at the current model."""
    model_name, model_version = _current_model()
    db.add(
        Embedding(
            user_id=highlight.user_id,
            content_type=ContentType.HIGHLIGHT.value,
            content_id=highlight.id,
            book_id=book.id,
            embedding=[0.1, 0.2],
            model_name=model_name,
            model_version=model_version,
            content_hash=hashlib.sha256(hashed_text.encode()).hexdigest(),
        )
    )
    await db.commit()


class TestBackfillReconciliation:
    async def test_enqueues_content_whose_hash_drifted_but_not_current_content(
        self,
        client: AsyncClient,
        override_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """ADR-0002's drift case: model matches, content changed underneath."""
        drifted = await _add_highlight(db_session, test_book, "the edited text")
        await _index(db_session, test_book, drifted, "the original text")
        current = await _add_highlight(db_session, test_book, "untouched text")
        await _index(db_session, test_book, current, "untouched text")

        with patch(ENABLED, return_value=True):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["total_jobs"] == 1
        enqueued = {call.kwargs["content_id"] for call in override_queue.enqueue.await_args_list}
        assert enqueued == {drifted.id}

    async def test_enqueues_orphaned_embedding_so_it_gets_pruned(
        self,
        client: AsyncClient,
        override_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """An embedding outliving its source is work: the job deletes it."""
        gone = await _add_highlight(db_session, test_book, "since deleted", deleted=True)
        await _index(db_session, test_book, gone, "since deleted")

        with patch(ENABLED, return_value=True):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["total_jobs"] == 1
        enqueued = {call.kwargs["content_id"] for call in override_queue.enqueue.await_args_list}
        assert enqueued == {gone.id}
