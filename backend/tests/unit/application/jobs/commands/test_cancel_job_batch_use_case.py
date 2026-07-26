"""Tests for CancelJobBatchUseCase."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.jobs.commands.cancel_job_batch_use_case import CancelJobBatchUseCase
from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchStatus, JobBatchType
from src.domain.jobs.exceptions import JobBatchNotFoundError


def _make_batch(
    batch_id: int = 1,
    status: JobBatchStatus = JobBatchStatus.RUNNING,
    job_keys: list[str] | None = None,
) -> JobBatch:
    now = datetime.now(UTC)
    return JobBatch.create_with_id(
        id=JobBatchId(batch_id),
        user_id=UserId(1),
        batch_type=JobBatchType.CHAPTER_PREREADING,
        reference_id="42",
        total_jobs=3,
        completed_jobs=1,
        failed_jobs=0,
        status=status,
        job_keys=job_keys or ["k1", "k2", "k3"],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def batch_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save.side_effect = lambda b: b
    return repo


@pytest.fixture
def queue_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(batch_repo: AsyncMock, queue_service: AsyncMock) -> CancelJobBatchUseCase:
    return CancelJobBatchUseCase(batch_repo=batch_repo, queue_service=queue_service)


class TestCancelJobBatch:
    async def test_aborts_all_jobs_and_cancels_batch(
        self,
        use_case: CancelJobBatchUseCase,
        batch_repo: AsyncMock,
        queue_service: AsyncMock,
    ) -> None:
        batch_repo.find_by_id.return_value = _make_batch()
        result = await use_case.execute(JobBatchId(1), UserId(1))
        assert result.status == JobBatchStatus.CANCELLED
        assert queue_service.abort.call_count == 3
        batch_repo.save.assert_called_once()

    async def test_raises_when_not_found(
        self, use_case: CancelJobBatchUseCase, batch_repo: AsyncMock
    ) -> None:
        batch_repo.find_by_id.return_value = None
        with pytest.raises(JobBatchNotFoundError):
            await use_case.execute(JobBatchId(999), UserId(1))
