"""SQLAlchemy repository for job batches."""

from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchStatus, JobBatchType
from src.domain.jobs.exceptions import ActiveJobBatchExistsError
from src.infrastructure.jobs.mappers.job_batch_mapper import JobBatchMapper
from src.infrastructure.jobs.orm.job_batch_model import JobBatchModel


class JobBatchRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, batch: JobBatch) -> JobBatch:
        """Persist a batch, translating the one-active-backfill index into a domain error.

        The index is the only unique constraint on the table, and the only
        batch type it covers is the backfill, so an integrity error inserting a
        backfill row means a second one is already active. Postgres and SQLite
        word that error differently, hence the type check rather than a match on
        the constraint name. An update is excluded because no row can collide
        with itself -- an integrity error there is some other fault, and
        reporting it as "a backfill is already running" would send the caller
        after a batch that does not exist.
        """
        existing_model: JobBatchModel | None = None
        if batch.id.value > 0:
            existing_model = await self._db.get(JobBatchModel, batch.id.value)

        model = JobBatchMapper.to_orm(batch, existing_model)
        if not existing_model:
            self._db.add(model)

        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            if not existing_model and batch.batch_type is JobBatchType.CONTENT_EMBEDDING_BACKFILL:
                raise ActiveJobBatchExistsError(batch.batch_type) from None
            raise

        await self._db.refresh(model)
        return JobBatchMapper.to_domain(model)

    async def atomic_increment_completed(self, batch_id: JobBatchId) -> JobBatch | None:
        """Atomically increment completed_jobs and recompute status in SQL."""
        return await self._atomic_increment(batch_id, "completed")

    async def atomic_increment_failed(self, batch_id: JobBatchId) -> JobBatch | None:
        """Atomically increment failed_jobs and recompute status in SQL."""
        return await self._atomic_increment(batch_id, "failed")

    async def _atomic_increment(self, batch_id: JobBatchId, field: str) -> JobBatch | None:
        increment_col = (
            JobBatchModel.completed_jobs if field == "completed" else JobBatchModel.failed_jobs
        )
        new_completed = JobBatchModel.completed_jobs + (1 if field == "completed" else 0)
        new_failed = JobBatchModel.failed_jobs + (1 if field == "failed" else 0)
        new_finished = new_completed + new_failed

        new_status = case(
            (
                JobBatchModel.status == JobBatchStatus.CANCELLED.value,
                JobBatchStatus.CANCELLED.value,
            ),
            (
                new_finished >= JobBatchModel.total_jobs,
                case(
                    (new_failed == JobBatchModel.total_jobs, JobBatchStatus.FAILED.value),
                    (new_failed > 0, JobBatchStatus.COMPLETED_WITH_ERRORS.value),
                    else_=JobBatchStatus.COMPLETED.value,
                ),
            ),
            (new_finished > 0, JobBatchStatus.RUNNING.value),
            else_=JobBatchModel.status,
        )

        stmt = (
            update(JobBatchModel)
            .where(JobBatchModel.id == batch_id.value)
            .values(
                **{increment_col.key: increment_col + 1},
                status=new_status,
            )
            .returning(JobBatchModel)
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        model = result.scalar_one_or_none()
        return JobBatchMapper.to_domain(model) if model else None

    async def find_by_id(self, batch_id: JobBatchId, user_id: UserId) -> JobBatch | None:
        result = await self._db.execute(
            select(JobBatchModel).where(
                JobBatchModel.id == batch_id.value,
                JobBatchModel.user_id == user_id.value,
            )
        )
        model = result.scalar_one_or_none()
        return JobBatchMapper.to_domain(model) if model else None
