"""Tests for JobBatch domain entity."""

from datetime import UTC, datetime

import pytest

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchStatus, JobBatchType


def _create(**overrides: object) -> JobBatch:
    defaults: dict[str, object] = {
        "user_id": UserId(1),
        "batch_type": JobBatchType.CHAPTER_DIGEST,
        "reference_id": "42",
        "total_jobs": 5,
    }
    defaults.update(overrides)
    return JobBatch.create(**defaults)  # type: ignore[arg-type]


class TestJobBatchCreate:
    def test_creates_with_defaults(self) -> None:
        batch = _create()
        assert batch.id == JobBatchId(0)
        assert batch.user_id == UserId(1)
        assert batch.batch_type == JobBatchType.CHAPTER_DIGEST
        assert batch.reference_id == "42"
        assert batch.total_jobs == 5
        assert batch.completed_jobs == 0
        assert batch.failed_jobs == 0
        assert batch.status == JobBatchStatus.PENDING
        assert batch.job_keys == []

    def test_rejects_zero_total_jobs(self) -> None:
        with pytest.raises(DomainError, match="total_jobs must be positive"):
            _create(total_jobs=0)

    def test_rejects_negative_total_jobs(self) -> None:
        with pytest.raises(DomainError, match="total_jobs must be positive"):
            _create(total_jobs=-1)

    def test_rejects_empty_reference_id(self) -> None:
        with pytest.raises(DomainError, match="reference_id cannot be empty"):
            _create(reference_id="")


class TestJobBatchMarkJobCompleted:
    def test_increments_completed(self) -> None:
        batch = _create(total_jobs=3)
        batch.mark_job_completed()
        assert batch.completed_jobs == 1
        assert batch.status == JobBatchStatus.RUNNING

    def test_transitions_to_completed_when_all_done(self) -> None:
        batch = _create(total_jobs=2)
        batch.mark_job_completed()
        batch.mark_job_completed()
        assert batch.completed_jobs == 2
        assert batch.status == JobBatchStatus.COMPLETED

    def test_completed_with_some_failures(self) -> None:
        batch = _create(total_jobs=3)
        batch.mark_job_completed()
        batch.mark_job_failed()
        batch.mark_job_completed()
        assert batch.status == JobBatchStatus.COMPLETED_WITH_ERRORS


class TestJobBatchMarkJobFailed:
    def test_increments_failed(self) -> None:
        batch = _create(total_jobs=3)
        batch.mark_job_failed()
        assert batch.failed_jobs == 1
        assert batch.status == JobBatchStatus.RUNNING

    def test_all_failed(self) -> None:
        batch = _create(total_jobs=2)
        batch.mark_job_failed()
        batch.mark_job_failed()
        assert batch.status == JobBatchStatus.FAILED


class TestJobBatchCancelledStaysCanelled:
    def test_completed_after_cancel_stays_cancelled(self) -> None:
        batch = _create(total_jobs=3)
        batch.cancel()
        batch.mark_job_completed()
        assert batch.status == JobBatchStatus.CANCELLED

    def test_failed_after_cancel_stays_cancelled(self) -> None:
        batch = _create(total_jobs=3)
        batch.cancel()
        batch.mark_job_failed()
        assert batch.status == JobBatchStatus.CANCELLED


class TestJobBatchCancel:
    def test_cancel_sets_cancelled(self) -> None:
        batch = _create(total_jobs=3)
        batch.cancel()
        assert batch.status == JobBatchStatus.CANCELLED

    def test_cancel_already_completed_raises(self) -> None:
        batch = _create(total_jobs=1)
        batch.mark_job_completed()
        with pytest.raises(DomainError, match=r"Cannot cancel.*COMPLETED"):
            batch.cancel()


class TestJobBatchAddJobKey:
    def test_adds_key(self) -> None:
        batch = _create()
        batch.add_job_key("saq:job:abc123")
        assert batch.job_keys == ["saq:job:abc123"]

    def test_adds_multiple_keys(self) -> None:
        batch = _create()
        batch.add_job_key("key1")
        batch.add_job_key("key2")
        assert batch.job_keys == ["key1", "key2"]


class TestJobBatchReconstitute:
    def test_create_with_id(self) -> None:
        now = datetime.now(UTC)
        batch = JobBatch.create_with_id(
            id=JobBatchId(10),
            user_id=UserId(1),
            batch_type=JobBatchType.CHAPTER_DIGEST,
            reference_id="42",
            total_jobs=5,
            completed_jobs=2,
            failed_jobs=1,
            status=JobBatchStatus.RUNNING,
            job_keys=["k1", "k2"],
            created_at=now,
            updated_at=now,
        )
        assert batch.id == JobBatchId(10)
        assert batch.completed_jobs == 2
        assert batch.failed_jobs == 1
        assert batch.status == JobBatchStatus.RUNNING
        assert batch.job_keys == ["k1", "k2"]
