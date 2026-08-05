"""How embedding work is cut into jobs, and how the ones never enqueued are counted.

Two paths enqueue embeddings -- the backfill reconciles a whole library, the
live enqueuer cuts a highlight upload -- and they have to agree on both halves
of this. On the slice size, because a slice is what the worker task takes; on
the accounting, because a batch reporting "completed" while slices were silently
dropped is worse than one reporting failures.
"""

from itertools import batched

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.domain.jobs.entities.job_batch import JobBatch

#: How many content units one embedding job handles.
#:
#: A job per unit meant a queue round trip per unit inside this request *and* a
#: provider round trip per unit in the worker; a slice amortises both. Well
#: below the client's own per-request cap (96, OpenRouter's limit, which the
#: client chunks at independently and which is not this layer's business):
#: a slice of long notes is a large payload to ask a local Ollama GPU to hold at
#: once, and 32 already removes 31 of every 32 requests.
EMBEDDING_SLICE_SIZE = 32


def slice_ids(content_ids: list[int]) -> list[list[int]]:
    """Cut one content type's ids into job-sized slices."""
    return [list(chunk) for chunk in batched(content_ids, EMBEDDING_SLICE_SIZE)]


async def record_dropped_slices(
    batch: JobBatch, expected_jobs: int, batch_repo: JobBatchRepositoryProtocol
) -> JobBatch:
    """Mark the slices an enqueue loop never reached as failed, then persist.

    Deliberately not ``total_jobs = len(job_keys)``. Shrinking the total let a
    backfill of 500 slices which broke at slice 3 terminate as "completed,
    total_jobs=3", with nothing to say 497 were dropped. Counting them as
    failures keeps the batch honest and still lets it reach a terminal status
    once the enqueued jobs report -- COMPLETED_WITH_ERRORS instead of COMPLETED.
    """
    for _ in range(expected_jobs - len(batch.job_keys)):
        batch.mark_job_failed()
    return await batch_repo.save(batch)
