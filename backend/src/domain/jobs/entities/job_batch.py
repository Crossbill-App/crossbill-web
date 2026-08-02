"""JobBatch domain entity for tracking groups of background jobs."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from src.domain.common.entity import Entity
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import JobBatchId, UserId


class JobBatchType(StrEnum):
    """Supported batch job types."""

    CHAPTER_DIGEST = "chapter_digest"
    CONTENT_EMBEDDING = "content_embedding"


class JobBatchStatus(StrEnum):
    """Status of a job batch."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_JOB_BATCH_STATUSES: frozenset[JobBatchStatus] = frozenset(
    {JobBatchStatus.PENDING, JobBatchStatus.RUNNING}
)
"""Statuses in which a batch still has jobs expected to run."""


@dataclass
class JobBatch(Entity[JobBatchId]):
    """Tracks a group of related background jobs."""

    id: JobBatchId
    user_id: UserId
    batch_type: JobBatchType
    reference_id: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    status: JobBatchStatus
    job_keys: list[str]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.total_jobs <= 0:
            raise DomainError("total_jobs must be positive")
        if not self.reference_id or not self.reference_id.strip():
            raise DomainError("reference_id cannot be empty")

    def _recompute_status(self) -> None:
        if self.status == JobBatchStatus.CANCELLED:
            return
        finished = self.completed_jobs + self.failed_jobs
        if finished >= self.total_jobs:
            if self.failed_jobs == self.total_jobs:
                self.status = JobBatchStatus.FAILED
            elif self.failed_jobs > 0:
                self.status = JobBatchStatus.COMPLETED_WITH_ERRORS
            else:
                self.status = JobBatchStatus.COMPLETED
        elif finished > 0:
            self.status = JobBatchStatus.RUNNING
        self.updated_at = datetime.now(UTC)

    def mark_job_completed(self) -> None:
        self.completed_jobs += 1
        self._recompute_status()

    def mark_job_failed(self) -> None:
        self.failed_jobs += 1
        self._recompute_status()

    def cancel(self) -> None:
        terminal = {
            JobBatchStatus.COMPLETED,
            JobBatchStatus.FAILED,
            JobBatchStatus.COMPLETED_WITH_ERRORS,
        }
        if self.status in terminal:
            raise DomainError(f"Cannot cancel batch in {self.status.upper()} status")
        self.status = JobBatchStatus.CANCELLED
        self.updated_at = datetime.now(UTC)

    def add_job_key(self, key: str) -> None:
        self.job_keys.append(key)

    @classmethod
    def create(
        cls,
        user_id: UserId,
        batch_type: JobBatchType,
        reference_id: str,
        total_jobs: int,
    ) -> "JobBatch":
        now = datetime.now(UTC)
        return cls(
            id=JobBatchId.generate(),
            user_id=user_id,
            batch_type=batch_type,
            reference_id=reference_id,
            total_jobs=total_jobs,
            completed_jobs=0,
            failed_jobs=0,
            status=JobBatchStatus.PENDING,
            job_keys=[],
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def create_with_id(
        cls,
        id: JobBatchId,
        user_id: UserId,
        batch_type: JobBatchType,
        reference_id: str,
        total_jobs: int,
        completed_jobs: int,
        failed_jobs: int,
        status: JobBatchStatus,
        job_keys: list[str],
        created_at: datetime,
        updated_at: datetime,
    ) -> "JobBatch":
        return cls(
            id=id,
            user_id=user_id,
            batch_type=batch_type,
            reference_id=reference_id,
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            status=status,
            job_keys=list(job_keys),
            created_at=created_at,
            updated_at=updated_at,
        )
