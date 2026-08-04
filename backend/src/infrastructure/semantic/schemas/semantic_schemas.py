"""Pydantic schemas for semantic-search API responses."""

from pydantic import BaseModel

from src.application.semantic.content_type import ContentType
from src.infrastructure.jobs.schemas.job_batch_schemas import JobBatchResponse


class BackfillResponse(BaseModel):
    """What a backfill request did.

    ``total_jobs`` is the field to key on, because it is the only one present in
    both outcomes: it is 0 exactly when nothing needed embedding, and then
    ``batch`` is null because no batch was created and there is nothing to poll.
    """

    total_jobs: int
    batch: JobBatchResponse | None


class SemanticSearchResult(BaseModel):
    content_type: ContentType
    content_id: int
    book_id: int | None
    score: float
    text: str
