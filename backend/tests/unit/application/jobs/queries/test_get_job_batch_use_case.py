"""Tests for GetJobBatchUseCase."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.jobs.queries.get_job_batch_use_case import GetJobBatchUseCase
from src.application.jobs.queries.job_batch import JobBatchView
from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatchStatus, JobBatchType
from src.domain.jobs.exceptions import JobBatchNotFoundError


def _make_view(batch_id: int = 1) -> JobBatchView:
    now = datetime.now(UTC)
    return JobBatchView(
        id=batch_id,
        batch_type=JobBatchType.CHAPTER_DIGEST,
        reference_id="42",
        total_jobs=5,
        completed_jobs=2,
        failed_jobs=0,
        status=JobBatchStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def job_batch_query() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(job_batch_query: AsyncMock) -> GetJobBatchUseCase:
    return GetJobBatchUseCase(job_batch_query=job_batch_query)


class TestGetJobBatch:
    async def test_returns_view(
        self, use_case: GetJobBatchUseCase, job_batch_query: AsyncMock
    ) -> None:
        job_batch_query.get_batch.return_value = _make_view(1)

        result = await use_case.execute(JobBatchId(1), UserId(1))

        assert result.id == 1
        job_batch_query.get_batch.assert_awaited_once_with(JobBatchId(1), UserId(1))

    async def test_raises_when_not_found(
        self, use_case: GetJobBatchUseCase, job_batch_query: AsyncMock
    ) -> None:
        job_batch_query.get_batch.return_value = None

        with pytest.raises(JobBatchNotFoundError):
            await use_case.execute(JobBatchId(999), UserId(1))
