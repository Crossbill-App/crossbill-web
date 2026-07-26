"""Use case for enqueuing batch prereading generation for a book."""

import structlog

from src.application.common.ownership import require_book
from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.reading.protocols.chapter_prereading_repository import (
    ChapterPrereadingRepositoryProtocol,
)
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchType

logger = structlog.get_logger(__name__)


class EnqueueBookPrereadingUseCase:
    def __init__(
        self,
        chapter_repo: ChapterRepositoryProtocol,
        book_repo: BookRepositoryProtocol,
        batch_repo: JobBatchRepositoryProtocol,
        queue_service: JobQueueServiceProtocol,
        prereading_repo: ChapterPrereadingRepositoryProtocol,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._book_repo = book_repo
        self._batch_repo = batch_repo
        self._queue_service = queue_service
        self._prereading_repo = prereading_repo

    async def execute(self, book_id: BookId, user_id: UserId) -> JobBatch:
        await require_book(self._book_repo, book_id, user_id)

        chapters = await self._chapter_repo.find_all_by_book(book_id, user_id)

        existing = await self._prereading_repo.find_all_by_book_id(book_id)
        already_generated = {p.chapter_id for p in existing}

        eligible = [ch for ch in chapters if ch.start_xpoint and ch.id not in already_generated]

        if not eligible:
            raise DomainError("No eligible chapters found for prereading generation")

        batch = JobBatch.create(
            user_id=user_id,
            batch_type=JobBatchType.CHAPTER_PREREADING,
            reference_id=str(book_id.value),
            total_jobs=len(eligible),
        )
        batch = await self._batch_repo.save(batch)

        for chapter in eligible:
            try:
                job_key = await self._queue_service.enqueue(
                    "generate_chapter_prereading",
                    retries=3,
                    timeout_seconds=300,
                    batch_id=batch.id.value,
                    book_id=book_id.value,
                    chapter_id=chapter.id.value,
                    user_id=user_id.value,
                )
                batch.add_job_key(job_key)
            except Exception:
                logger.exception(
                    "failed_to_enqueue_job",
                    chapter_id=chapter.id.value,
                    batch_id=batch.id.value,
                )
                break

        if not batch.job_keys:
            batch.cancel()
            await self._batch_repo.save(batch)
            raise DomainError("Failed to enqueue any jobs for prereading generation")

        batch.total_jobs = min(batch.total_jobs, len(batch.job_keys))

        await self._batch_repo.save(batch)

        logger.info(
            "book_prereading_batch_enqueued",
            batch_id=batch.id.value,
            book_id=book_id.value,
            total_jobs=batch.total_jobs,
        )
        return batch
