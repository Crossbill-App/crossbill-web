"""Application service that enqueues embedding jobs, gated by the feature flag.

A fire-and-forget side effect of a write: it no-ops when embeddings are
disabled and swallows enqueue failures, since the backfill reconciles a missed
embedding later and a create or upload must never fail over one.

Call it *after* the repository save -- the repositories commit inside
``save``/``bulk_save``, so a job starting immediately still reads the new row.
The queue mechanics live in ``batching``; only this path's policy is here.
"""

import structlog

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.semantic.batching import (
    enqueue_embedding_batch,
    enqueue_embedding_job,
    slice_ids,
)
from src.application.semantic.content_type import ContentType
from src.config import Settings
from src.domain.common.value_objects.ids import UserId

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
        """Enqueue one unit as a bare job -- no batch.

        A single edit has no progress worth reporting, and a batch row per note
        save would mean one row per keystroke-sized change.
        """
        if not self._settings.embeddings_enabled:
            return

        try:
            await enqueue_embedding_job(content_type, [content_id], user_id, self._queue_service)
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

        A highlight upload can carry hundreds of units -- the one write path
        where progress is worth reporting.
        """
        if not self._settings.embeddings_enabled or not content_ids:
            return

        try:
            batch = await enqueue_embedding_batch(
                [(content_type, content_slice) for content_slice in slice_ids(content_ids)],
                user_id=UserId(user_id),
                reference_id=reference_id,
                queue_service=self._queue_service,
                batch_repo=self._batch_repo,
            )
        except Exception:
            # enqueue_embedding_batch already tolerates a failing enqueue; this
            # catches everything around it, above all persisting the batch.
            logger.exception(
                "failed_to_enqueue_embedding_batch",
                content_type=content_type.value,
                reference_id=reference_id,
            )
            return

        # Getting nowhere is already logged per slice and leaves a CANCELLED
        # batch -- nothing to raise about, the highlights are saved.
        if batch.job_keys:
            logger.info(
                "content_embedding_batch_enqueued",
                batch_id=batch.id.value,
                reference_id=reference_id,
                content_type=content_type.value,
                total_jobs=batch.total_jobs,
            )
