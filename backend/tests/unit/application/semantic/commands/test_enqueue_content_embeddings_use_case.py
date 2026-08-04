"""Tests for EnqueueContentEmbeddingsUseCase (backfill)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.semantic.commands.enqueue_content_embeddings_use_case import (
    EMBEDDING_SLICE_SIZE,
    EnqueueContentEmbeddingsUseCase,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import WorkItem
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.jobs.entities.job_batch import JobBatchType
from src.domain.reading.exceptions import BookNotFoundError


@pytest.fixture
def content_source() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def batch_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save.side_effect = lambda b: b
    return repo


@pytest.fixture
def queue_service() -> AsyncMock:
    service = AsyncMock()
    service.enqueue = AsyncMock(
        side_effect=lambda fn, **kw: f"saq:{kw['content_type']}:{min(kw['content_ids'])}"
    )
    return service


@pytest.fixture
def book_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(
    content_source: AsyncMock,
    batch_repo: AsyncMock,
    queue_service: AsyncMock,
    book_repo: AsyncMock,
) -> EnqueueContentEmbeddingsUseCase:
    return EnqueueContentEmbeddingsUseCase(
        content_source=content_source,
        batch_repo=batch_repo,
        queue_service=queue_service,
        book_repo=book_repo,
    )


class TestEnqueueContentEmbeddings:
    async def test_enqueues_one_job_per_content_type_when_all_fit_one_slice(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        queue_service: AsyncMock,
    ) -> None:
        """Three units of three types are three jobs — because a slice never mixes types."""
        content_source.iter_work_items.return_value = [
            WorkItem(ContentType.NOTE, 1),
            WorkItem(ContentType.HIGHLIGHT, 2),
            WorkItem(ContentType.DIGEST, 3),
        ]

        batch = await use_case.execute(UserId(1), None)
        assert batch is not None

        assert batch.total_jobs == 3
        assert batch.batch_type == JobBatchType.CONTENT_EMBEDDING
        assert batch.reference_id == "user:1"
        assert len(batch.job_keys) == 3
        assert queue_service.enqueue.call_count == 3
        assert [call.kwargs["content_ids"] for call in queue_service.enqueue.await_args_list] == [
            [1],
            [2],
            [3],
        ]

    async def test_packs_units_of_one_type_into_slices(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        queue_service: AsyncMock,
    ) -> None:
        """The whole point: N units cost ceil(N / slice) jobs, not N."""
        units = EMBEDDING_SLICE_SIZE * 2 + 5
        content_source.iter_work_items.return_value = [
            WorkItem(ContentType.HIGHLIGHT, content_id) for content_id in range(units)
        ]

        batch = await use_case.execute(UserId(1), None)
        assert batch is not None

        assert batch.total_jobs == 3
        assert queue_service.enqueue.call_count == 3
        sizes = [len(call.kwargs["content_ids"]) for call in queue_service.enqueue.await_args_list]
        assert sizes == [EMBEDDING_SLICE_SIZE, EMBEDDING_SLICE_SIZE, 5]
        enqueued = [
            content_id
            for call in queue_service.enqueue.await_args_list
            for content_id in call.kwargs["content_ids"]
        ]
        assert enqueued == list(range(units))

    async def test_never_mixes_content_types_within_a_slice(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        queue_service: AsyncMock,
    ) -> None:
        """A job resolves its ids through one type's table, so a mixed slice would lose rows."""
        content_source.iter_work_items.return_value = [
            WorkItem(ContentType.NOTE, 1),
            WorkItem(ContentType.HIGHLIGHT, 2),
            WorkItem(ContentType.NOTE, 3),
        ]

        await use_case.execute(UserId(1), None)

        by_type = {
            call.kwargs["content_type"]: call.kwargs["content_ids"]
            for call in queue_service.enqueue.await_args_list
        }
        assert by_type == {"note": [1, 3], "highlight": [2]}

    async def test_records_slices_it_could_not_enqueue_as_failures(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        queue_service: AsyncMock,
    ) -> None:
        """total_jobs counts slices, so the failure accounting has to as well."""
        content_source.iter_work_items.return_value = [
            WorkItem(ContentType.NOTE, content_id) for content_id in range(EMBEDDING_SLICE_SIZE * 3)
        ]
        queue_service.enqueue.side_effect = ["saq:note:0", RuntimeError("queue is down")]

        batch = await use_case.execute(UserId(1), None)
        assert batch is not None

        assert batch.total_jobs == 3
        assert len(batch.job_keys) == 1
        assert batch.failed_jobs == 2

    async def test_scopes_to_book_and_checks_ownership(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        book_repo: AsyncMock,
    ) -> None:
        book_repo.find_by_id.return_value = MagicMock()
        content_source.iter_work_items.return_value = [WorkItem(ContentType.HIGHLIGHT, 5)]

        batch = await use_case.execute(UserId(1), BookId(9))
        assert batch is not None

        assert batch.reference_id == "9"
        content_source.iter_work_items.assert_awaited_once_with(1, 9)

    async def test_raises_when_book_not_found(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        book_repo: AsyncMock,
    ) -> None:
        book_repo.find_by_id.return_value = None

        with pytest.raises(BookNotFoundError):
            await use_case.execute(UserId(1), BookId(404))

    async def test_returns_none_when_nothing_to_embed(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        batch_repo: AsyncMock,
        queue_service: AsyncMock,
    ) -> None:
        """Everything already indexed is an outcome, not an error.

        No batch is created for it either — a batch of nothing would be a row
        that exists only to say nothing happened, and JobBatch forbids
        total_jobs of 0 anyway.
        """
        content_source.iter_work_items.return_value = []

        assert await use_case.execute(UserId(1), None) is None

        batch_repo.save.assert_not_called()
        queue_service.enqueue.assert_not_called()
