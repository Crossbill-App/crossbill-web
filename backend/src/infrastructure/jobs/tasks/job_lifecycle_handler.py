"""SAQ lifecycle handler for updating JobBatch progress."""

from datetime import UTC, datetime

import structlog
from saq import Job
from saq.types import Context

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.domain.common.value_objects.ids import JobBatchId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchStatus

logger = structlog.get_logger(__name__)

_TERMINAL_COMPLETE = "complete"
_TERMINAL_FAILED = "failed"
_TERMINAL_ABORTED = "aborted"

_TERMINAL_BATCH_STATUSES = frozenset(
    {JobBatchStatus.COMPLETED, JobBatchStatus.COMPLETED_WITH_ERRORS, JobBatchStatus.FAILED}
)
"""CANCELLED is deliberately excluded: a cancelled batch keeps this status
through every remaining increment, so emitting on it would log one
"finished" event per straggler job instead of exactly once."""


class JobLifecycleHandler:
    def __init__(self, batch_repo: JobBatchRepositoryProtocol) -> None:
        self._batch_repo = batch_repo

    async def after_process(self, ctx: Context) -> None:
        job: Job | None = ctx.get("job")  # type: ignore[assignment]
        if job is None:
            return
        batch_id = (job.kwargs or {}).get("batch_id")
        if batch_id is None:
            return

        status = job.status
        if status not in (_TERMINAL_COMPLETE, _TERMINAL_FAILED, _TERMINAL_ABORTED):
            return

        bid = JobBatchId(batch_id)
        if status == _TERMINAL_COMPLETE:
            batch = await self._batch_repo.atomic_increment_completed(bid)
        else:
            batch = await self._batch_repo.atomic_increment_failed(bid)

        if not batch:
            logger.warning("batch_not_found_in_after_process", batch_id=batch_id)
            return

        logger.info(
            "batch_progress_updated",
            batch_id=batch_id,
            completed=batch.completed_jobs,
            failed=batch.failed_jobs,
            total=batch.total_jobs,
            status=batch.status,
        )

        if batch.status in _TERMINAL_BATCH_STATUSES:
            self._log_batch_finished(batch)

    @staticmethod
    def _log_batch_finished(batch: JobBatch) -> None:
        """Emit the one terminal event per batch, leveled by outcome.

        Fires exactly once: only the increment that finishes the last job
        returns a terminal status, and no further increments arrive after it.
        """
        if batch.status is JobBatchStatus.FAILED:
            log = logger.error
        elif batch.status is JobBatchStatus.COMPLETED_WITH_ERRORS:
            log = logger.warning
        else:
            log = logger.info

        # SQLite hands back naive datetimes even for timezone-aware columns.
        created_at = batch.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        log(
            "batch_finished",
            batch_id=batch.id.value,
            batch_type=batch.batch_type.value,
            reference_id=batch.reference_id,
            status=batch.status,
            total=batch.total_jobs,
            completed=batch.completed_jobs,
            failed=batch.failed_jobs,
            duration_seconds=round((datetime.now(UTC) - created_at).total_seconds(), 1),
        )
