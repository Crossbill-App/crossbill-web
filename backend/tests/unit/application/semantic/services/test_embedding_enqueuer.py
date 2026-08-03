"""Tests for EmbeddingEnqueuer (the fire-and-forget live-ingestion seam)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.semantic.content_type import ContentType
from src.application.semantic.services.embedding_enqueuer import EmbeddingEnqueuer
from src.domain.jobs.entities.job_batch import JobBatchStatus, JobBatchType


@pytest.fixture
def queue_service() -> AsyncMock:
    service = AsyncMock()
    service.enqueue = AsyncMock(
        side_effect=lambda fn, **kw: f"saq:{kw['content_type']}:{kw['content_id']}"
    )
    return service


@pytest.fixture
def batch_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save.side_effect = lambda b: b
    return repo


def _settings(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(embeddings_enabled=enabled)


def _enqueuer(
    queue_service: AsyncMock, batch_repo: AsyncMock, *, enabled: bool
) -> EmbeddingEnqueuer:
    return EmbeddingEnqueuer(
        queue_service=queue_service,
        batch_repo=batch_repo,
        settings=_settings(enabled=enabled),  # type: ignore[arg-type]
    )


class TestEnqueueFor:
    async def test_noop_when_disabled(
        self, queue_service: AsyncMock, batch_repo: AsyncMock
    ) -> None:
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=False)

        await enqueuer.enqueue_for(ContentType.NOTE, 1, 5)

        queue_service.enqueue.assert_not_called()

    async def test_enqueues_single_job_without_batch_id(
        self, queue_service: AsyncMock, batch_repo: AsyncMock
    ) -> None:
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=True)

        await enqueuer.enqueue_for(ContentType.NOTE, 42, 5)

        queue_service.enqueue.assert_awaited_once()
        _, kwargs = queue_service.enqueue.call_args
        assert kwargs["content_type"] == "note"
        assert kwargs["content_id"] == 42
        assert kwargs["user_id"] == 5
        assert "batch_id" not in kwargs
        batch_repo.save.assert_not_called()

    async def test_swallows_enqueue_failure(
        self, queue_service: AsyncMock, batch_repo: AsyncMock
    ) -> None:
        queue_service.enqueue.side_effect = RuntimeError("queue down")
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=True)

        await enqueuer.enqueue_for(ContentType.DIGEST, 3, 5)


class TestEnqueueMany:
    async def test_noop_when_disabled(
        self, queue_service: AsyncMock, batch_repo: AsyncMock
    ) -> None:
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=False)

        await enqueuer.enqueue_many(ContentType.HIGHLIGHT, [1, 2], 5, reference_id="9")

        queue_service.enqueue.assert_not_called()
        batch_repo.save.assert_not_called()

    async def test_noop_when_empty(self, queue_service: AsyncMock, batch_repo: AsyncMock) -> None:
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=True)

        await enqueuer.enqueue_many(ContentType.HIGHLIGHT, [], 5, reference_id="9")

        queue_service.enqueue.assert_not_called()
        batch_repo.save.assert_not_called()

    async def test_creates_batch_and_enqueues_each_with_batch_id(
        self, queue_service: AsyncMock, batch_repo: AsyncMock
    ) -> None:
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=True)

        await enqueuer.enqueue_many(ContentType.HIGHLIGHT, [10, 11, 12], 5, reference_id="9")

        assert queue_service.enqueue.call_count == 3
        saved_batch = batch_repo.save.call_args_list[0].args[0]
        assert saved_batch.batch_type == JobBatchType.CONTENT_EMBEDDING
        assert saved_batch.reference_id == "9"
        assert saved_batch.total_jobs == 3
        for call in queue_service.enqueue.call_args_list:
            assert call.kwargs["batch_id"] == saved_batch.id.value
            assert call.kwargs["content_type"] == "highlight"
            assert call.kwargs["user_id"] == 5

    async def test_cancels_batch_when_nothing_enqueued(
        self, queue_service: AsyncMock, batch_repo: AsyncMock
    ) -> None:
        queue_service.enqueue.side_effect = RuntimeError("queue down")
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=True)

        await enqueuer.enqueue_many(ContentType.HIGHLIGHT, [10, 11], 5, reference_id="9")

        saved_batch = batch_repo.save.call_args_list[-1].args[0]
        assert saved_batch.status == JobBatchStatus.CANCELLED

    async def test_swallows_batch_save_failure(
        self, queue_service: AsyncMock, batch_repo: AsyncMock
    ) -> None:
        batch_repo.save.side_effect = RuntimeError("db down")
        enqueuer = _enqueuer(queue_service, batch_repo, enabled=True)

        await enqueuer.enqueue_many(ContentType.HIGHLIGHT, [10], 5, reference_id="9")
