"""Use case for enqueuing a backfill batch of content embeddings."""

import structlog

from src.application.common.ownership import require_book
from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.semantic.protocols.content_source import ContentSourceProtocol
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchType

logger = structlog.get_logger(__name__)


class EnqueueContentEmbeddingsUseCase:
    """Reconciles the user's content against the index and enqueues one job per gap."""

    def __init__(
        self,
        content_source: ContentSourceProtocol,
        batch_repo: JobBatchRepositoryProtocol,
        queue_service: JobQueueServiceProtocol,
        book_repo: BookRepositoryProtocol,
    ) -> None:
        self._content_source = content_source
        self._batch_repo = batch_repo
        self._queue_service = queue_service
        self._book_repo = book_repo

    async def execute(self, user_id: UserId, book_id: BookId | None) -> JobBatch:
        if book_id is not None:
            await require_book(self._book_repo, book_id, user_id)

        items = await self._content_source.iter_work_items(
            user_id.value, book_id.value if book_id else None
        )
        if not items:
            raise DomainError("No content units need embedding")

        reference_id = str(book_id.value) if book_id else f"user:{user_id.value}"
        batch = JobBatch.create(
            user_id=user_id,
            batch_type=JobBatchType.CONTENT_EMBEDDING,
            reference_id=reference_id,
            total_jobs=len(items),
        )
        batch = await self._batch_repo.save(batch)

        for item in items:
            try:
                job_key = await self._queue_service.enqueue(
                    "generate_content_embedding",
                    retries=3,
                    timeout_seconds=300,
                    batch_id=batch.id.value,
                    content_type=item.content_type.value,
                    content_id=item.content_id,
                    user_id=user_id.value,
                )
                batch.add_job_key(job_key)
            except Exception:
                logger.exception(
                    "failed_to_enqueue_job",
                    content_type=item.content_type.value,
                    content_id=item.content_id,
                    batch_id=batch.id.value,
                )
                break

        if not batch.job_keys:
            batch.cancel()
            await self._batch_repo.save(batch)
            raise DomainError("Failed to enqueue any jobs for content embedding")

        batch.total_jobs = min(batch.total_jobs, len(batch.job_keys))

        await self._batch_repo.save(batch)

        logger.info(
            "content_embedding_batch_enqueued",
            batch_id=batch.id.value,
            reference_id=reference_id,
            total_jobs=batch.total_jobs,
        )
        return batch
