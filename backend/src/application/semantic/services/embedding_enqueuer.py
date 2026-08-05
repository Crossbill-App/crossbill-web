"""Application service that enqueues embedding jobs, gated by the feature flag.

Called from source-module write use cases as a fire-and-forget side effect of a
save. It no-ops when embeddings are disabled and swallows enqueue failures -- a
missed embedding is reconciled later by the backfill path, and must never fail
the user's create or upload.

Callers invoke it *after* the repository save, not before: the repositories
commit inside ``save``/``bulk_save``, so a job that starts running the instant
it is enqueued still reads committed content rather than the pre-edit row.
"""

import structlog

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.semantic.batching import record_dropped_slices, slice_ids
from src.application.semantic.content_type import ContentType
from src.config import Settings
from src.domain.common.value_objects.ids import UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchType

logger = structlog.get_logger(__name__)

_TASK = "generate_content_embeddings"
_RETRIES = 3
_TIMEOUT_SECONDS = 300


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
        """Enqueue one unit as a bare job -- no batch.

        A single edit has no progress worth reporting, and a JobBatch per note
        save would put a row in the batch table for every keystroke-sized
        change. The worker task's ``batch_id`` is optional for exactly this.
        """
        if not self._settings.embeddings_enabled:
            return

        try:
            await self._queue_service.enqueue(
                _TASK,
                retries=_RETRIES,
                timeout_seconds=_TIMEOUT_SECONDS,
                content_type=content_type.value,
                content_ids=[content_id],
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
        """Enqueue many units of one type as a tracked batch of slices.

        A highlight upload can carry hundreds of units, so this is the one write
        path where progress is worth reporting -- and where the slice size
        actually bites.
        """
        if not self._settings.embeddings_enabled or not content_ids:
            return

        try:
            await self._enqueue_batch(content_type, content_ids, user_id, reference_id)
        except Exception:
            # The inner loop already tolerates a failing enqueue; this catches
            # everything around it (persisting the batch, above all), because
            # the caller's write has committed and must not be reported failed.
            logger.exception(
                "failed_to_enqueue_embedding_batch",
                content_type=content_type.value,
                reference_id=reference_id,
            )

    async def _enqueue_batch(
        self,
        content_type: ContentType,
        content_ids: list[int],
        user_id: int,
        reference_id: str,
    ) -> None:
        slices = slice_ids(content_ids)
        batch = JobBatch.create(
            user_id=UserId(user_id),
            batch_type=JobBatchType.CONTENT_EMBEDDING,
            reference_id=reference_id,
            total_jobs=len(slices),
        )
        batch = await self._batch_repo.save(batch)

        for content_slice in slices:
            try:
                job_key = await self._queue_service.enqueue(
                    _TASK,
                    retries=_RETRIES,
                    timeout_seconds=_TIMEOUT_SECONDS,
                    batch_id=batch.id.value,
                    content_type=content_type.value,
                    content_ids=content_slice,
                    user_id=user_id,
                )
                batch.add_job_key(job_key)
            except Exception:
                logger.exception(
                    "failed_to_enqueue_embedding",
                    content_type=content_type.value,
                    content_ids=content_slice,
                    batch_id=batch.id.value,
                )
                break

        if not batch.job_keys:
            # Unlike the backfill, which raises so the user learns the button did
            # nothing, this is a side effect of a write that already succeeded.
            batch.cancel()
            await self._batch_repo.save(batch)
            return

        batch = await record_dropped_slices(batch, len(slices), self._batch_repo)

        logger.info(
            "content_embedding_batch_enqueued",
            batch_id=batch.id.value,
            reference_id=reference_id,
            content_type=content_type.value,
            total_jobs=batch.total_jobs,
        )
