"""Tests for EnqueueContentEmbeddingsUseCase (backfill)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.semantic.commands.enqueue_content_embeddings_use_case import (
    EnqueueContentEmbeddingsUseCase,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import WorkItem
from src.domain.common.exceptions import DomainError
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
        side_effect=lambda fn, **kw: f"saq:{kw['content_type']}:{kw['content_id']}"
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
    async def test_enqueues_one_job_per_work_item(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        queue_service: AsyncMock,
    ) -> None:
        content_source.iter_work_items.return_value = [
            WorkItem(ContentType.NOTE, 1),
            WorkItem(ContentType.HIGHLIGHT, 2),
            WorkItem(ContentType.DIGEST, 3),
        ]

        batch = await use_case.execute(UserId(1), None)

        assert batch.total_jobs == 3
        assert batch.batch_type == JobBatchType.CONTENT_EMBEDDING
        assert batch.reference_id == "user:1"
        assert len(batch.job_keys) == 3
        assert queue_service.enqueue.call_count == 3

    async def test_scopes_to_book_and_checks_ownership(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
        book_repo: AsyncMock,
    ) -> None:
        book_repo.find_by_id.return_value = MagicMock()
        content_source.iter_work_items.return_value = [WorkItem(ContentType.HIGHLIGHT, 5)]

        batch = await use_case.execute(UserId(1), BookId(9))

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

    async def test_raises_when_nothing_to_embed(
        self,
        use_case: EnqueueContentEmbeddingsUseCase,
        content_source: AsyncMock,
    ) -> None:
        content_source.iter_work_items.return_value = []

        with pytest.raises(DomainError, match="No content units"):
            await use_case.execute(UserId(1), None)
