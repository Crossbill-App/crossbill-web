"""How embedding work is cut into jobs and handed to the queue as a tracked batch.

Two paths enqueue embeddings -- the backfill reconciles a whole library, the
live enqueuer cuts a highlight upload -- and they must agree on all of it: the
slice size, because a slice is what the worker task takes; the enqueue kwargs,
because they are a contract with ``generate_content_embeddings``; and the
bookkeeping, because a batch reporting "completed" while slices were silently
dropped is worse than one reporting failures.

What the two paths do *not* share is what to do when nothing lands at all. The
backfill raises, so the user learns the button did nothing; the live enqueuer
returns quietly, because it is a side effect of a write that already succeeded.
So this returns the batch and lets each caller read ``job_keys`` and decide.
"""

from itertools import batched

import structlog

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.semantic.content_type import ContentType
from src.domain.common.value_objects.ids import UserId
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchType

logger = structlog.get_logger(__name__)

#: How many content units one embedding job handles.
#:
#: A job per unit meant a queue round trip per unit inside this request *and* a
#: provider round trip per unit in the worker; a slice amortises both. Well
#: below the client's own per-request cap (96, OpenRouter's limit, which the
#: client chunks at independently and which is not this layer's business):
#: a slice of long notes is a large payload to ask a local Ollama GPU to hold at
#: once, and 32 already removes 31 of every 32 requests.
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

    Stops at the first slice that fails to enqueue: a queue that just rejected
    one job is unlikely to accept the next, and continuing would spend the
    request's remaining time finding that out. The batch is returned either way
    -- with empty ``job_keys`` when nothing landed, which is the caller's signal
    that it got nowhere.
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

    Same task and same kwargs as the batched path minus ``batch_id``, which the
    task takes as optional precisely so a single edit does not need a batch row
    to report the progress of its one job.
    """
    await queue_service.enqueue(
        _TASK,
        retries=_RETRIES,
        timeout_seconds=_TIMEOUT_SECONDS,
        content_type=content_type.value,
        content_ids=content_ids,
        user_id=user_id,
    )
