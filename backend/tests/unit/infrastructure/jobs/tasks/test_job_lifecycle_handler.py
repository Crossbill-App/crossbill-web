"""Tests for JobLifecycleHandler."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchStatus, JobBatchType
from src.infrastructure.jobs.tasks.job_lifecycle_handler import JobLifecycleHandler


def _make_batch(batch_id: int = 1, total: int = 3, completed: int = 0) -> JobBatch:
    now = datetime.now(UTC)
    return JobBatch.create_with_id(
        id=JobBatchId(batch_id),
        user_id=UserId(1),
        batch_type=JobBatchType.CHAPTER_DIGEST,
        reference_id="42",
        total_jobs=total,
        completed_jobs=completed,
        failed_jobs=0,
        status=JobBatchStatus.PENDING,
        job_keys=[],
        created_at=now,
        updated_at=now,
    )


def _make_ctx_with_job(status: str, batch_id: int | None = 1) -> dict[str, object]:
    job = MagicMock()
    job.status = status
    job.kwargs = {"batch_id": batch_id} if batch_id is not None else {"some_key": "value"}
    return {"job": job}


@pytest.fixture
def batch_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def handler(batch_repo: AsyncMock) -> JobLifecycleHandler:
    return JobLifecycleHandler(batch_repo=batch_repo)


class TestAfterProcess:
    async def test_calls_atomic_increment_completed_on_success(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch_repo.atomic_increment_completed.return_value = _make_batch(completed=1)
        ctx = _make_ctx_with_job("complete")

        await handler.after_process(ctx)  # type: ignore[arg-type]

        batch_repo.atomic_increment_completed.assert_called_once_with(JobBatchId(1))

    async def test_calls_atomic_increment_failed_on_failure(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch_repo.atomic_increment_failed.return_value = _make_batch()
        ctx = _make_ctx_with_job("failed")

        await handler.after_process(ctx)  # type: ignore[arg-type]

        batch_repo.atomic_increment_failed.assert_called_once_with(JobBatchId(1))

    async def test_calls_atomic_increment_failed_on_aborted(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch_repo.atomic_increment_failed.return_value = _make_batch()
        ctx = _make_ctx_with_job("aborted")

        await handler.after_process(ctx)  # type: ignore[arg-type]

        batch_repo.atomic_increment_failed.assert_called_once_with(JobBatchId(1))

    async def test_skips_jobs_without_batch_id(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        ctx = _make_ctx_with_job("complete", batch_id=None)

        await handler.after_process(ctx)  # type: ignore[arg-type]

        batch_repo.atomic_increment_completed.assert_not_called()
        batch_repo.atomic_increment_failed.assert_not_called()

    async def test_skips_non_terminal_status(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        ctx = _make_ctx_with_job("active")

        await handler.after_process(ctx)  # type: ignore[arg-type]

        batch_repo.atomic_increment_completed.assert_not_called()
        batch_repo.atomic_increment_failed.assert_not_called()

    async def test_skips_when_no_job_in_context(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        await handler.after_process({})  # type: ignore[arg-type]

        batch_repo.atomic_increment_completed.assert_not_called()
