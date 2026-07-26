"""Tests for job batch API endpoints."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.domain.jobs.entities.job_batch import JobBatchStatus, JobBatchType
from src.infrastructure.jobs.orm.job_batch_model import JobBatchModel
from src.models import Book, User

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2


async def _add_batch(
    db_session: AsyncSession,
    reference_id: str,
    batch_status: JobBatchStatus = JobBatchStatus.RUNNING,
    user_id: int = DEFAULT_USER_ID,
    created_at: datetime | None = None,
) -> JobBatchModel:
    stamp = created_at or datetime.now(UTC)
    batch = JobBatchModel(
        user_id=user_id,
        batch_type=JobBatchType.CHAPTER_PREREADING.value,
        reference_id=reference_id,
        total_jobs=3,
        completed_jobs=1,
        failed_jobs=0,
        status=batch_status.value,
        job_keys=["key-1"],
        created_at=stamp,
        updated_at=stamp,
    )
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)
    return batch


class TestGetJobBatch:
    """Test suite for GET /jobs/batches/{batch_id} endpoint."""

    async def test_returns_batch_progress(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        batch = await _add_batch(db_session, reference_id="42")

        response = await client.get(f"/api/v1/jobs/batches/{batch.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == batch.id
        assert data["batch_type"] == "chapter_prereading"
        assert data["reference_id"] == "42"
        assert data["total_jobs"] == 3
        assert data["completed_jobs"] == 1
        assert data["failed_jobs"] == 0
        assert data["status"] == "running"
        assert set(data) == {
            "id",
            "batch_type",
            "reference_id",
            "total_jobs",
            "completed_jobs",
            "failed_jobs",
            "status",
            "created_at",
            "updated_at",
        }

    async def test_returns_404_for_unknown_batch(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/jobs/batches/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_returns_404_for_another_users_batch(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
        await db_session.commit()
        batch = await _add_batch(db_session, reference_id="42", user_id=OTHER_USER_ID)

        response = await client.get(f"/api/v1/jobs/batches/{batch.id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetActiveBookPrereadingBatch:
    """Test suite for GET /jobs/books/{book_id}/prereading endpoint."""

    async def test_returns_null_when_no_batch_exists(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        response = await client.get(f"/api/v1/jobs/books/{test_book.id}/prereading")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None

    async def test_returns_the_newest_active_batch(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        now = datetime.now(UTC)
        await _add_batch(
            db_session,
            reference_id=str(test_book.id),
            batch_status=JobBatchStatus.COMPLETED,
            created_at=now,
        )
        await _add_batch(
            db_session,
            reference_id=str(test_book.id),
            batch_status=JobBatchStatus.RUNNING,
            created_at=now - timedelta(hours=2),
        )
        newest_active = await _add_batch(
            db_session,
            reference_id=str(test_book.id),
            batch_status=JobBatchStatus.PENDING,
            created_at=now - timedelta(hours=1),
        )

        response = await client.get(f"/api/v1/jobs/books/{test_book.id}/prereading")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == newest_active.id

    async def test_ignores_finished_batches(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await _add_batch(
            db_session,
            reference_id=str(test_book.id),
            batch_status=JobBatchStatus.CANCELLED,
        )

        response = await client.get(f"/api/v1/jobs/books/{test_book.id}/prereading")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None
