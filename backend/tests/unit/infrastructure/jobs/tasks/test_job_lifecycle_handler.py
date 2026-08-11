"""Tests for JobLifecycleHandler."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from structlog.testing import capture_logs
from structlog.typing import EventDict

from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchStatus, JobBatchType
from src.infrastructure.jobs.tasks.job_lifecycle_handler import JobLifecycleHandler


def _make_batch(
    batch_id: int = 1,
    total: int = 3,
    completed: int = 0,
    failed: int = 0,
    status: JobBatchStatus = JobBatchStatus.PENDING,
) -> JobBatch:
    now = datetime.now(UTC)
    return JobBatch.create_with_id(
        id=JobBatchId(batch_id),
        user_id=UserId(1),
        batch_type=JobBatchType.CHAPTER_DIGEST,
        reference_id="42",
        total_jobs=total,
        completed_jobs=completed,
        failed_jobs=failed,
        status=status,
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


class TestBatchFinishedEvent:
    async def _finished_events(
        self,
        handler: JobLifecycleHandler,
        batch_repo: AsyncMock,
        batch: JobBatch,
    ) -> list[EventDict]:
        batch_repo.atomic_increment_completed.return_value = batch
        with capture_logs() as captured:
            await handler.after_process(_make_ctx_with_job("complete"))  # type: ignore[arg-type]
        return [e for e in captured if e["event"] == "batch_finished"]

    async def test_completed_batch_emits_info(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch = _make_batch(total=3, completed=3, status=JobBatchStatus.COMPLETED)

        events = await self._finished_events(handler, batch_repo, batch)

        assert len(events) == 1
        event = events[0]
        assert event["log_level"] == "info"
        assert event["batch_id"] == 1
        assert event["batch_type"] == "chapter_digest"
        assert event["total"] == 3
        assert event["completed"] == 3
        assert event["failed"] == 0
        duration = event["duration_seconds"]
        assert isinstance(duration, float)
        assert duration >= 0

    async def test_completed_with_errors_emits_warning(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch = _make_batch(
            total=3, completed=2, failed=1, status=JobBatchStatus.COMPLETED_WITH_ERRORS
        )

        events = await self._finished_events(handler, batch_repo, batch)

        assert len(events) == 1
        assert events[0]["log_level"] == "warning"
        assert events[0]["failed"] == 1

    async def test_failed_batch_emits_error(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch = _make_batch(total=3, failed=3, status=JobBatchStatus.FAILED)

        events = await self._finished_events(handler, batch_repo, batch)

        assert len(events) == 1
        assert events[0]["log_level"] == "error"
        assert events[0]["failed"] == 3

    async def test_running_batch_emits_nothing(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch = _make_batch(total=3, completed=1, status=JobBatchStatus.RUNNING)

        assert await self._finished_events(handler, batch_repo, batch) == []

    async def test_cancelled_batch_emits_nothing(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch = _make_batch(total=3, completed=1, failed=1, status=JobBatchStatus.CANCELLED)

        assert await self._finished_events(handler, batch_repo, batch) == []

    async def test_naive_created_at_still_yields_duration(
        self, handler: JobLifecycleHandler, batch_repo: AsyncMock
    ) -> None:
        batch = _make_batch(total=1, completed=1, status=JobBatchStatus.COMPLETED)
        batch.created_at = datetime.now(UTC).replace(tzinfo=None)

        events = await self._finished_events(handler, batch_repo, batch)

        duration = events[0]["duration_seconds"]
        assert isinstance(duration, float)
        assert duration >= 0
