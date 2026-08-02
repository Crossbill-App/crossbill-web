"""Tests for the job-batch read model."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatchStatus, JobBatchType
from src.infrastructure.jobs.orm.job_batch_model import JobBatchModel
from src.infrastructure.jobs.queries.job_batch_query import JobBatchQuery
from src.models import User

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2
BOOK_REFERENCE = "42"


@pytest.fixture
def query(db_session: AsyncSession) -> JobBatchQuery:
    """The query service wired the way the container wires it."""
    return JobBatchQuery(db=db_session)


async def add_batch(
    db_session: AsyncSession,
    status: JobBatchStatus = JobBatchStatus.PENDING,
    user_id: int = DEFAULT_USER_ID,
    reference_id: str = BOOK_REFERENCE,
    created_at: datetime | None = None,
    total_jobs: int = 3,
    completed_jobs: int = 0,
    failed_jobs: int = 0,
    job_keys: list[str] | None = None,
) -> JobBatchModel:
    """Insert a job batch row directly, bypassing the write side."""
    batch = JobBatchModel(
        user_id=user_id,
        batch_type=JobBatchType.CHAPTER_DIGEST.value,
        reference_id=reference_id,
        total_jobs=total_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        status=status.value,
        job_keys=job_keys if job_keys is not None else [],
        created_at=created_at or datetime.now(UTC),
        updated_at=created_at or datetime.now(UTC),
    )
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)
    return batch


async def test_get_batch_returns_the_progress_counters(
    query: JobBatchQuery, db_session: AsyncSession
) -> None:
    batch = await add_batch(
        db_session,
        status=JobBatchStatus.RUNNING,
        total_jobs=5,
        completed_jobs=2,
        failed_jobs=1,
        job_keys=["k1", "k2"],
    )

    view = await query.get_batch(JobBatchId(batch.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    assert view.id == batch.id
    assert view.batch_type == JobBatchType.CHAPTER_DIGEST
    assert view.reference_id == BOOK_REFERENCE
    assert (view.total_jobs, view.completed_jobs, view.failed_jobs) == (5, 2, 1)
    assert view.status == JobBatchStatus.RUNNING
    assert view.created_at == batch.created_at
    assert view.updated_at == batch.updated_at


async def test_get_batch_returns_none_for_an_unknown_batch(query: JobBatchQuery) -> None:
    assert await query.get_batch(JobBatchId(999), UserId(DEFAULT_USER_ID)) is None


async def test_get_batch_hides_another_users_batch(
    query: JobBatchQuery, db_session: AsyncSession, other_user: User
) -> None:
    batch = await add_batch(db_session, user_id=OTHER_USER_ID)

    assert await query.get_batch(JobBatchId(batch.id), UserId(DEFAULT_USER_ID)) is None


@pytest.mark.parametrize(
    "status",
    [JobBatchStatus.PENDING, JobBatchStatus.RUNNING],
)
async def test_active_statuses_are_returned(
    query: JobBatchQuery, db_session: AsyncSession, status: JobBatchStatus
) -> None:
    await add_batch(db_session, status=status)

    view = await query.get_active_for_reference(
        JobBatchType.CHAPTER_DIGEST, BOOK_REFERENCE, UserId(DEFAULT_USER_ID)
    )

    assert view is not None
    assert view.status == status


@pytest.mark.parametrize(
    "status",
    [
        JobBatchStatus.COMPLETED,
        JobBatchStatus.COMPLETED_WITH_ERRORS,
        JobBatchStatus.FAILED,
        JobBatchStatus.CANCELLED,
    ],
)
async def test_finished_batches_are_not_active(
    query: JobBatchQuery, db_session: AsyncSession, status: JobBatchStatus
) -> None:
    await add_batch(db_session, status=status)

    view = await query.get_active_for_reference(
        JobBatchType.CHAPTER_DIGEST, BOOK_REFERENCE, UserId(DEFAULT_USER_ID)
    )

    assert view is None


async def test_the_newest_active_batch_wins(query: JobBatchQuery, db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    await add_batch(db_session, status=JobBatchStatus.RUNNING, created_at=now - timedelta(hours=2))
    await add_batch(db_session, status=JobBatchStatus.COMPLETED, created_at=now)
    newest_active = await add_batch(
        db_session, status=JobBatchStatus.PENDING, created_at=now - timedelta(hours=1)
    )

    view = await query.get_active_for_reference(
        JobBatchType.CHAPTER_DIGEST, BOOK_REFERENCE, UserId(DEFAULT_USER_ID)
    )

    assert view is not None
    assert view.id == newest_active.id


async def test_another_books_batch_is_not_returned(
    query: JobBatchQuery, db_session: AsyncSession
) -> None:
    await add_batch(db_session, status=JobBatchStatus.RUNNING, reference_id="99")

    view = await query.get_active_for_reference(
        JobBatchType.CHAPTER_DIGEST, BOOK_REFERENCE, UserId(DEFAULT_USER_ID)
    )

    assert view is None


async def test_another_users_active_batch_is_invisible(
    query: JobBatchQuery, db_session: AsyncSession, other_user: User
) -> None:
    await add_batch(db_session, status=JobBatchStatus.RUNNING, user_id=OTHER_USER_ID)

    view = await query.get_active_for_reference(
        JobBatchType.CHAPTER_DIGEST, BOOK_REFERENCE, UserId(DEFAULT_USER_ID)
    )

    assert view is None
