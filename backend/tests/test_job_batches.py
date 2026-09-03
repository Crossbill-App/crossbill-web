"""Tests for job batch API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.domain.jobs.entities.job_batch import JobBatchStatus, JobBatchType
from src.infrastructure.jobs.orm.job_batch_model import JobBatchModel
from src.models import Book, Chapter, ChapterDigest, User

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
        batch_type=JobBatchType.CHAPTER_DIGEST.value,
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


async def _add_digestible_chapter(
    db_session: AsyncSession, book: Book, name: str, chapter_number: int
) -> Chapter:
    chapter = Chapter(
        book_id=book.id,
        name=name,
        chapter_number=chapter_number,
        start_xpoint=f"/body/chapter[{chapter_number}]",
    )
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


async def _add_digest(db_session: AsyncSession, chapter: Chapter) -> ChapterDigest:
    digest = ChapterDigest(
        chapter_id=chapter.id,
        summary=f"Old summary for {chapter.name}",
        keypoints=["Old key point"],
        questions=[
            {
                "question": "Old question?",
                "answer": "Old answer",
                "user_answer": "My saved answer",
            }
        ],
        generated_at=datetime.now(UTC),
        ai_model="old-model",
    )
    db_session.add(digest)
    await db_session.commit()
    await db_session.refresh(digest)
    return digest


async def _seed_book_with_existing_and_missing(
    db_session: AsyncSession, book: Book
) -> tuple[Chapter, Chapter]:
    existing = await _add_digestible_chapter(db_session, book, "Existing", 1)
    missing = await _add_digestible_chapter(db_session, book, "Missing", 2)
    await _add_digest(db_session, existing)
    return existing, missing


class TestEnqueueBookDigest:
    """POST /jobs/books/{book_id}/digest chooses which chapters to enqueue."""

    async def test_default_still_skips_existing_summaries(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        ai_enabled: None,
        job_queue: AsyncMock,
    ) -> None:
        _, missing = await _seed_book_with_existing_and_missing(db_session, test_book)

        response = await client.post(f"/api/v1/jobs/books/{test_book.id}/digest")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["total_jobs"] == 1
        assert [call.kwargs["chapter_id"] for call in job_queue.enqueue.await_args_list] == [
            missing.id
        ]

    async def test_overwrite_enqueues_existing_and_missing_summaries(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        ai_enabled: None,
        job_queue: AsyncMock,
    ) -> None:
        existing, missing = await _seed_book_with_existing_and_missing(db_session, test_book)
        db_session.add(Chapter(book_id=test_book.id, name="No EPUB position"))
        await db_session.commit()

        response = await client.post(
            f"/api/v1/jobs/books/{test_book.id}/digest",
            params={"overwrite_existing": "true"},
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        batch = response.json()
        assert batch["total_jobs"] == 2
        assert {call.kwargs["chapter_id"] for call in job_queue.enqueue.await_args_list} == {
            existing.id,
            missing.id,
        }

        active = await client.get(f"/api/v1/jobs/books/{test_book.id}/digest")
        assert active.status_code == status.HTTP_200_OK
        assert active.json()["id"] == batch["id"]
        assert active.json()["total_jobs"] == 2

    async def test_overwrite_does_not_enqueue_another_users_book(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        ai_enabled: None,
        job_queue: AsyncMock,
    ) -> None:
        db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
        await db_session.commit()
        other_book = Book(user_id=OTHER_USER_ID, title="Private Book")
        db_session.add(other_book)
        await db_session.commit()
        await db_session.refresh(other_book)
        await _add_digestible_chapter(db_session, other_book, "Private Chapter", 1)

        response = await client.post(
            f"/api/v1/jobs/books/{other_book.id}/digest",
            params={"overwrite_existing": "true"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        job_queue.enqueue.assert_not_awaited()


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
        assert data["batch_type"] == "chapter_digest"
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


class TestGetActiveBookDigestBatch:
    """Test suite for GET /jobs/books/{book_id}/digest endpoint."""

    async def test_returns_null_when_no_batch_exists(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        response = await client.get(f"/api/v1/jobs/books/{test_book.id}/digest")

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

        response = await client.get(f"/api/v1/jobs/books/{test_book.id}/digest")

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

        response = await client.get(f"/api/v1/jobs/books/{test_book.id}/digest")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None
