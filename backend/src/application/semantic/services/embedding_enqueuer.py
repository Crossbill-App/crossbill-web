"""Application service that enqueues embedding jobs, gated by the feature flag.

Called from source-module write use cases as a fire-and-forget side effect of a
save. It no-ops when embeddings are disabled and swallows enqueue failures — a
missed embedding is reconciled later by the backfill path, and must never fail
the user's create/upload.
"""

import structlog

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.semantic.content_type import ContentType
from src.config import Settings
from src.domain.common.value_objects.ids import UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchType

logger = structlog.get_logger(__name__)


class EmbeddingEnqueuer:
    """Enqueues embedding jobs for content units, gated by ``embeddings_enabled``."""

    def __init__(
        self,
        queue_service: JobQueueServiceProtocol,
        batch_repo: JobBatchRepositoryProtocol,
        settings: Settings,
    ) -> None:
        self._queue_service = queue_service
        self._batch_repo = batch_repo
        self._settings = settings

    async def enqueue_for(self, content_type: ContentType, content_id: int, user_id: int) -> None:
        if not self._settings.embeddings_enabled:
            return

        try:
            await self._queue_service.enqueue(
                "generate_content_embedding",
                retries=3,
                timeout_seconds=300,
                content_type=content_type.value,
                content_id=content_id,
                user_id=user_id,
            )
        except Exception:
            logger.exception(
                "failed_to_enqueue_embedding",
                content_type=content_type.value,
                content_id=content_id,
            )

    async def enqueue_many(
        self,
        content_type: ContentType,
        content_ids: list[int],
        user_id: int,
        reference_id: str,
    ) -> None:
        if not self._settings.embeddings_enabled or not content_ids:
            return

        try:
            batch = JobBatch.create(
                user_id=UserId(user_id),
                batch_type=JobBatchType.CONTENT_EMBEDDING,
                reference_id=reference_id,
                total_jobs=len(content_ids),
            )
            batch = await self._batch_repo.save(batch)

            for content_id in content_ids:
                try:
                    job_key = await self._queue_service.enqueue(
                        "generate_content_embedding",
                        retries=3,
                        timeout_seconds=300,
                        batch_id=batch.id.value,
                        content_type=content_type.value,
                        content_id=content_id,
                        user_id=user_id,
                    )
                    batch.add_job_key(job_key)
                except Exception:
                    logger.exception(
                        "failed_to_enqueue_embedding",
                        content_type=content_type.value,
                        content_id=content_id,
                        batch_id=batch.id.value,
                    )
                    break

            if not batch.job_keys:
                batch.cancel()
                await self._batch_repo.save(batch)
                return

            batch.total_jobs = min(batch.total_jobs, len(batch.job_keys))
            await self._batch_repo.save(batch)
        except Exception:
            logger.exception(
                "failed_to_enqueue_embedding_batch",
                content_type=content_type.value,
                reference_id=reference_id,
            )
