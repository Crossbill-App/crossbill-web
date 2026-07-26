"""Read model for the job-batch progress views.

This is a view DTO, not a domain entity: it exists to be rendered and must never
be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatchStatus, JobBatchType


@dataclass(frozen=True)
class JobBatchView:
    """A batch's progress as the API reports it -- counters, not job keys."""

    id: int
    batch_type: JobBatchType
    reference_id: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    status: JobBatchStatus
    created_at: dt
    updated_at: dt


class JobBatchQueryProtocol(Protocol):
    async def get_batch(self, batch_id: JobBatchId, user_id: UserId) -> JobBatchView | None: ...

    async def get_active_for_reference(
        self, batch_type: JobBatchType, reference_id: str, user_id: UserId
    ) -> JobBatchView | None:
        """Return the newest batch for the reference that is still active."""
        ...
