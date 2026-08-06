"""How embedding work is cut into jobs and handed to the queue as a tracked batch.

Shared by the backfill and the live enqueuer so the slice size, the enqueue
kwargs (a contract with ``generate_content_embeddings``) and the batch
bookkeeping stay in one place. The two differ only in what to do when nothing
lands, so this returns the batch and lets each caller read ``job_keys``.
"""

from itertools import batched

import structlog

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.semantic.content_type import ContentType
from src.domain.common.value_objects.ids import UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchType

logger = structlog.get_logger(__name__)

#: How many content units one embedding job handles. A slice amortises both the
#: queue and the provider round trip. Kept well below the client's own 96-unit
#: cap, which it chunks at independently: a slice of long notes is a large
#: payload for a local Ollama GPU, and 32 already removes 31 of every 32 calls.
EMBEDDING_SLICE_SIZE = 32

_TASK = "generate_content_embeddings"
_RETRIES = 3
_TIMEOUT_SECONDS = 300


def slice_ids(content_ids: list[int]) -> list[list[int]]:
    """Cut one content type's ids into job-sized slices."""
    return [list(chunk) for chunk in batched(content_ids, EMBEDDING_SLICE_SIZE)]


async def enqueue_embedding_batch(
    slices: list[tuple[ContentType, list[int]]],
    user_id: UserId,
    reference_id: str,
    queue_service: JobQueueServiceProtocol,
    batch_repo: JobBatchRepositoryProtocol,
) -> JobBatch:
    """Open a batch, enqueue one job per slice, and persist what actually landed.

    Stops at the first failed enqueue -- a queue that just rejected one job is
    unlikely to accept the next. Empty ``job_keys`` on the returned batch is the
    caller's signal that nothing landed.
    """
    batch = JobBatch.create(
        user_id=user_id,
        batch_type=JobBatchType.CONTENT_EMBEDDING,
        reference_id=reference_id,
        total_jobs=len(slices),
    )
    batch = await batch_repo.save(batch)

    for content_type, content_ids in slices:
        try:
            job_key = await queue_service.enqueue(
                _TASK,
                retries=_RETRIES,
                timeout_seconds=_TIMEOUT_SECONDS,
                batch_id=batch.id.value,
                content_type=content_type.value,
                content_ids=content_ids,
                user_id=user_id.value,
            )
            batch.add_job_key(job_key)
        except Exception:
            logger.exception(
                "failed_to_enqueue_embedding_job",
                content_type=content_type.value,
                content_ids=content_ids,
                batch_id=batch.id.value,
            )
            break

    if not batch.job_keys:
        batch.cancel()
        return await batch_repo.save(batch)

    batch.mark_unenqueued_jobs_failed()
    return await batch_repo.save(batch)


async def enqueue_embedding_job(
    content_type: ContentType,
    content_ids: list[int],
    user_id: int,
    queue_service: JobQueueServiceProtocol,
) -> None:
    """Enqueue one slice as a bare job, outside any batch.

    Same task and kwargs as the batched path minus ``batch_id``, which the task
    takes as optional so a single edit needs no batch row.
    """
    await queue_service.enqueue(
        _TASK,
        retries=_RETRIES,
        timeout_seconds=_TIMEOUT_SECONDS,
        content_type=content_type.value,
        content_ids=content_ids,
        user_id=user_id,
    )
