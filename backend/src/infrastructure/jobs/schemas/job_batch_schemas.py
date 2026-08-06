"""Pydantic schemas for job batch API responses.

The two converters live here rather than in a router because both the jobs and
the semantic router answer with batches, from the write side and the read side
respectively.
"""

from datetime import datetime

from pydantic import BaseModel

from src.application.jobs.queries.job_batch import JobBatchView
from src.domain.jobs.entities.job_batch import JobBatch


class JobBatchResponse(BaseModel):
    id: int
    batch_type: str
    reference_id: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    status: str
    created_at: datetime
    updated_at: datetime


def batch_to_response(batch: JobBatch) -> JobBatchResponse:
    return JobBatchResponse(
        id=batch.id.value,
        batch_type=batch.batch_type.value,
        reference_id=batch.reference_id,
        total_jobs=batch.total_jobs,
        completed_jobs=batch.completed_jobs,
        failed_jobs=batch.failed_jobs,
        status=batch.status.value,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def view_to_response(view: JobBatchView) -> JobBatchResponse:
    return JobBatchResponse(
        id=view.id,
        batch_type=view.batch_type.value,
        reference_id=view.reference_id,
        total_jobs=view.total_jobs,
        completed_jobs=view.completed_jobs,
        failed_jobs=view.failed_jobs,
        status=view.status.value,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )
