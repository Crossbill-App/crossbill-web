"""Tests for the POST /semantic/backfill ingestion endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.domain.jobs.entities.job_batch import JobBatchStatus, JobBatchType
from src.infrastructure.jobs.orm.job_batch_model import JobBatchModel
from src.models import Book, Highlight, User
from tests.conftest import CreateBookFunc, create_test_highlight
from tests.semantic_helpers import (
    backfill_enqueued_ids,
    embeddings_disabled,
    embeddings_enabled,
    plant_indexed_highlight,
    upload_highlights,
)

OTHER_USER_ID = 2

#: Patch target for the slice size, so a test can force several slices without
#: planting 33 highlights to get past the real one.
SLICE_SIZE = "src.application.semantic.batching.EMBEDDING_SLICE_SIZE"


class TestBackfillEndpoint:
    async def test_blocked_when_embeddings_disabled(
        self, client: AsyncClient, job_queue: AsyncMock
    ) -> None:
        with embeddings_disabled():
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        job_queue.enqueue.assert_not_called()

    async def test_enqueues_a_batch_when_enabled(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        test_book: Book,
        test_highlight: Highlight,
    ) -> None:
        with embeddings_enabled():
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["total_jobs"] >= 1
        assert data["batch"]["batch_type"] == "content_embedding_backfill"
        assert data["batch"]["status"] == "pending"
        job_queue.enqueue.assert_awaited()

    async def test_reports_nothing_to_do_without_failing_the_request(
        self, client: AsyncClient, job_queue: AsyncMock, db_session: AsyncSession
    ) -> None:
        """Pressing backfill twice is normal, so the second press is not an error.

        This answered 400 before, carrying the generic "The request could not be
        processed." — a caller could not tell "already indexed" from a malformed
        request. The status is pinned exactly, and so is total_jobs: 200 alone
        would not say which outcome it was.
        """
        with embeddings_enabled():
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_jobs"] == 0
        assert data["batch"] is None
        job_queue.enqueue.assert_not_called()

    async def test_packs_units_into_one_job_per_slice(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
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
            enqueued = await backfill_enqueued_ids(client, job_queue)

        assert len(enqueued) == 5
        assert job_queue.enqueue.await_count == 3

    async def test_records_slices_it_could_not_enqueue_as_failures(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
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
        job_queue.enqueue.side_effect = ["saq:1", RuntimeError("queue is down")]

        with embeddings_enabled(), patch(SLICE_SIZE, 1):
            response = await client.post("/api/v1/semantic/backfill")

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["total_jobs"] == 3
        assert data["batch"]["failed_jobs"] == 2
        assert data["batch"]["status"] == "running"


class TestOneBackfillAtATime:
    """The guard from issue #531: a double-tap must not double the bill."""

    async def test_refuses_a_second_backfill_while_one_is_running(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        test_book: Book,
        test_highlight: Highlight,
    ) -> None:
        with embeddings_enabled():
            first = await client.post("/api/v1/semantic/backfill")
            second = await client.post("/api/v1/semantic/backfill")

        assert first.status_code == status.HTTP_202_ACCEPTED
        assert second.status_code == status.HTTP_409_CONFLICT
        assert second.json()["error"] == "conflict"
        # The point of the guard: the refused request enqueued nothing, so the
        # units the first backfill picked up are not paid for twice.
        assert job_queue.enqueue.await_count == 1

    async def test_refuses_a_book_backfill_while_a_library_one_is_running(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        test_book: Book,
        test_highlight: Highlight,
    ) -> None:
        """The two carry different reference ids but overlapping content."""
        with embeddings_enabled():
            await client.post("/api/v1/semantic/backfill")
            scoped = await client.post(f"/api/v1/semantic/backfill?book_id={test_book.id}")

        assert scoped.status_code == status.HTTP_409_CONFLICT
        assert job_queue.enqueue.await_count == 1

    async def test_cancelling_the_running_backfill_clears_the_way(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        test_book: Book,
        test_highlight: Highlight,
    ) -> None:
        """Why the guard is not a lockout: a stranded batch is one request away.

        Without this the ADR's original objection stands -- a backfill that
        never reaches a terminal status would block every later one.
        """
        with embeddings_enabled():
            first = await client.post("/api/v1/semantic/backfill")
            batch_id = first.json()["batch"]["id"]
            refused = await client.post("/api/v1/semantic/backfill")

            cancelled = await client.delete(f"/api/v1/jobs/batches/{batch_id}")
            second = await client.post("/api/v1/semantic/backfill")

        assert refused.status_code == status.HTTP_409_CONFLICT
        assert cancelled.status_code == status.HTTP_200_OK
        assert cancelled.json()["status"] == "cancelled"
        assert second.status_code == status.HTTP_202_ACCEPTED
        assert second.json()["batch"]["id"] != batch_id

    async def test_an_upload_still_enqueues_while_a_backfill_is_running(
        self,
        client: AsyncClient,
        plugin_client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
        test_highlight: Highlight,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Uploads keep their own batch type, so the guard cannot refuse content.

        A single ``CONTENT_EMBEDDING`` type for both paths would make a running
        backfill reject the batch an upload opens, and the uploaded highlights
        would go unembedded until the next reconcile.
        """
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})

        with embeddings_enabled():
            backfill = await client.post("/api/v1/semantic/backfill")
            await upload_highlights(plugin_client, "book-1", "fresh one", "fresh two")

        assert backfill.status_code == status.HTTP_202_ACCEPTED
        uploaded = {
            content_id
            for call in job_queue.enqueue.await_args_list[1:]
            for content_id in call.kwargs["content_ids"]
        }
        assert len(uploaded) == 2

        batch_types = (await db_session.execute(select(JobBatchModel.batch_type))).scalars().all()
        assert sorted(batch_types) == ["content_embedding", "content_embedding_backfill"]


class TestActiveBackfillEndpoint:
    """GET /semantic/backfill/active -- how a client finds what a 409 refers to."""

    async def test_blocked_when_embeddings_disabled(self, client: AsyncClient) -> None:
        """Gated like every other route here: no provider, nothing to say about a backfill."""
        with embeddings_disabled():
            response = await client.get("/api/v1/semantic/backfill/active")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_returns_null_when_nothing_is_running(self, client: AsyncClient) -> None:
        with embeddings_enabled():
            response = await client.get("/api/v1/semantic/backfill/active")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None

    async def test_returns_the_running_backfill(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        test_book: Book,
        test_highlight: Highlight,
    ) -> None:
        with embeddings_enabled():
            started = await client.post("/api/v1/semantic/backfill")
            response = await client.get("/api/v1/semantic/backfill/active")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == started.json()["batch"]["id"]
        assert data["batch_type"] == "content_embedding_backfill"
        assert data["status"] == "pending"

    async def test_ignores_a_batch_an_upload_opened(
        self,
        client: AsyncClient,
        plugin_client: AsyncClient,
        job_queue: AsyncMock,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})

        with embeddings_enabled():
            await upload_highlights(plugin_client, "book-1", "just uploaded")
            response = await client.get("/api/v1/semantic/backfill/active")

        assert response.json() is None

    async def test_ignores_another_users_backfill(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        now = datetime.now(UTC)
        db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
        await db_session.flush()
        db_session.add(
            JobBatchModel(
                user_id=OTHER_USER_ID,
                batch_type=JobBatchType.CONTENT_EMBEDDING_BACKFILL.value,
                reference_id=f"user:{OTHER_USER_ID}",
                total_jobs=2,
                completed_jobs=0,
                failed_jobs=0,
                status=JobBatchStatus.RUNNING.value,
                job_keys=["saq:1"],
                created_at=now,
                updated_at=now,
            )
        )
        await db_session.commit()

        with embeddings_enabled():
            response = await client.get("/api/v1/semantic/backfill/active")

        assert response.json() is None


class TestBackfillReconciliation:
    async def test_enqueues_content_whose_hash_drifted_but_not_current_content(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """ADR-0002's drift case: model matches, content changed underneath."""
        drifted = await plant_indexed_highlight(
            db_session, test_book, "the edited text", hashed_text="the original text"
        )
        await plant_indexed_highlight(db_session, test_book, "untouched text")

        assert await backfill_enqueued_ids(client, job_queue) == {drifted.id}

    async def test_enqueues_orphaned_embedding_so_it_gets_pruned(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """An embedding outliving its source is work: the job deletes it."""
        gone = await plant_indexed_highlight(db_session, test_book, "since deleted", deleted=True)

        assert await backfill_enqueued_ids(client, job_queue) == {gone.id}
