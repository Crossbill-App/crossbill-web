"""Tests for the POST /semantic/backfill ingestion endpoint."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.models import Book, Highlight
from tests.semantic_helpers import ENABLED, backfill_enqueued_ids, plant_indexed_highlight


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


class TestBackfillReconciliation:
    async def test_enqueues_content_whose_hash_drifted_but_not_current_content(
        self,
        client: AsyncClient,
        override_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """ADR-0002's drift case: model matches, content changed underneath."""
        drifted = await plant_indexed_highlight(
            db_session, test_book, "the edited text", hashed_text="the original text"
        )
        await plant_indexed_highlight(db_session, test_book, "untouched text")

        assert await backfill_enqueued_ids(client, override_queue) == {drifted.id}

    async def test_enqueues_orphaned_embedding_so_it_gets_pruned(
        self,
        client: AsyncClient,
        override_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """An embedding outliving its source is work: the job deletes it."""
        gone = await plant_indexed_highlight(db_session, test_book, "since deleted", deleted=True)

        assert await backfill_enqueued_ids(client, override_queue) == {gone.id}
