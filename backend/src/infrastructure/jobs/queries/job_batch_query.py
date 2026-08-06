"""Query adapter for the job-batch progress views.

Rows map straight to view DTOs: no aggregate is loaded, so the ``job_keys`` blob
that only the write side needs never leaves the database. "Which statuses count
as active" is a domain fact, so the filter reuses
``ACTIVE_JOB_BATCH_STATUSES`` instead of restating the set in SQL.
"""

from datetime import datetime as dt

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.application.jobs.queries.job_batch import JobBatchView
from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import (
    ACTIVE_JOB_BATCH_STATUSES,
    JobBatchStatus,
    JobBatchType,
)
from src.infrastructure.jobs.orm.job_batch_model import JobBatchModel

_ViewRow = tuple[int, str, str, int, int, int, str, dt, dt]


def _select_view() -> Select[_ViewRow]:
    return select(
        JobBatchModel.id,
        JobBatchModel.batch_type,
        JobBatchModel.reference_id,
        JobBatchModel.total_jobs,
        JobBatchModel.completed_jobs,
        JobBatchModel.failed_jobs,
        JobBatchModel.status,
        JobBatchModel.created_at,
        JobBatchModel.updated_at,
    )


def _to_view(row: _ViewRow) -> JobBatchView:
    (
        batch_id,
        batch_type,
        reference_id,
        total_jobs,
        completed_jobs,
        failed_jobs,
        status,
        created_at,
        updated_at,
    ) = row
    return JobBatchView(
        id=batch_id,
        batch_type=JobBatchType(batch_type),
        reference_id=reference_id,
        total_jobs=total_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        status=JobBatchStatus(status),
        created_at=created_at,
        updated_at=updated_at,
    )


class JobBatchQuery:
    """Serves the job-batch read model from purpose-built selects."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_batch(self, batch_id: JobBatchId, user_id: UserId) -> JobBatchView | None:
        """Return one of the user's batches, or ``None`` when they have no such batch."""
        result = await self.db.execute(
            _select_view().where(
                JobBatchModel.id == batch_id.value,
                JobBatchModel.user_id == user_id.value,
            )
        )
        row = result.tuples().first()
        return _to_view(row) if row else None

    async def get_active_for_reference(
        self, batch_type: JobBatchType, reference_id: str, user_id: UserId
    ) -> JobBatchView | None:
        """Return the newest batch for the reference that is still active."""
        return await self._newest_active(
            batch_type, user_id, JobBatchModel.reference_id == reference_id
        )

    async def get_active_for_user(
        self, batch_type: JobBatchType, user_id: UserId
    ) -> JobBatchView | None:
        """Return the user's active batch of this type, across all references.

        How a client finds the batch to cancel after a backfill was refused: the
        409 says only that one is running, and for backfills the index
        guarantees this returns at most one row.
        """
        return await self._newest_active(batch_type, user_id)

    async def _newest_active(
        self,
        batch_type: JobBatchType,
        user_id: UserId,
        *conditions: ColumnElement[bool],
    ) -> JobBatchView | None:
        result = await self.db.execute(
            _select_view()
            .where(
                JobBatchModel.batch_type == batch_type.value,
                JobBatchModel.user_id == user_id.value,
                JobBatchModel.status.in_(sorted(s.value for s in ACTIVE_JOB_BATCH_STATUSES)),
                *conditions,
            )
            .order_by(JobBatchModel.created_at.desc())
            .limit(1)
        )
        row = result.tuples().first()
        return _to_view(row) if row else None
