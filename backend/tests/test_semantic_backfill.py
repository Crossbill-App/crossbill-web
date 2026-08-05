"""Tests for the POST /semantic/backfill ingestion endpoint."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.models import Book, Highlight
from tests.conftest import contract_checked_queue, create_test_highlight
from tests.semantic_helpers import ENABLED, backfill_enqueued_ids, plant_indexed_highlight

#: Patch target for the slice size, so a test can force several slices without
#: planting 33 highlights to get past the real one.
SLICE_SIZE = "src.application.semantic.batching.EMBEDDING_SLICE_SIZE"


@pytest.fixture
async def override_queue() -> AsyncGenerator[AsyncMock, None]:
    """Override the SAQ queue service (normally wired by the app lifespan).

    Uses the shared contract-checked fake rather than a bare AsyncMock, so a
    mismatch between this enqueue site and the worker task it names fails here.
    """
    from src.core import container  # noqa: PLC0415

    fake = contract_checked_queue()
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
        assert data["total_jobs"] >= 1
        assert data["batch"]["batch_type"] == "content_embedding"
        assert data["batch"]["status"] == "pending"
        override_queue.enqueue.assert_awaited()

    async def test_reports_nothing_to_do_without_failing_the_request(
        self, client: AsyncClient, override_queue: AsyncMock, db_session: AsyncSession
    ) -> None:
        """Pressing backfill twice is normal, so the second press is not an error.

        This answered 400 before, carrying the generic "The request could not be
        processed." — a caller could not tell "already indexed" from a malformed
        request. The status is pinned exactly, and so is total_jobs: 200 alone
        would not say which outcome it was.
        """
        with patch(ENABLED, return_value=True):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_jobs"] == 0
        assert data["batch"] is None
        override_queue.enqueue.assert_not_called()

    async def test_packs_units_into_one_job_per_slice(
        self,
        client: AsyncClient,
        override_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A backfill of N units costs ceil(N / slice) jobs, not N.

        One job per unit meant one queue round trip per unit in this request and
        one provider round trip per unit in the worker.
        """
        for index in range(5):
            await create_test_highlight(
                db_session,
                test_book,
                test_book.user_id,
                text=f"highlight {index}",
                datetime_str="2024-01-15 14:30:22",
            )

        with patch(SLICE_SIZE, 2):
            enqueued = await backfill_enqueued_ids(client, override_queue)

        assert len(enqueued) == 5
        assert override_queue.enqueue.await_count == 3

    async def test_records_slices_it_could_not_enqueue_as_failures(
        self,
        client: AsyncClient,
        override_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A backfill that breaks partway must not report the rest as done.

        Shrinking total_jobs to what was enqueued made the batch terminate as
        completed, with nothing to say the remaining slices were dropped.
        """
        for text in ("first", "second", "third"):
            await create_test_highlight(
                db_session,
                test_book,
                test_book.user_id,
                text=text,
                datetime_str="2024-01-15 14:30:22",
            )
        override_queue.enqueue.side_effect = ["saq:1", RuntimeError("queue is down")]

        with patch(ENABLED, return_value=True), patch(SLICE_SIZE, 1):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["total_jobs"] == 3
        assert data["batch"]["failed_jobs"] == 2
        assert data["batch"]["status"] == "running"


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
