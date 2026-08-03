"""API router for semantic-search ingestion (backfill)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.semantic.commands.enqueue_content_embeddings_use_case import (
    EnqueueContentEmbeddingsUseCase,
)
from src.core import container
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.identity import User
from src.domain.jobs.entities.job_batch import JobBatch
from src.infrastructure.common.dependencies import require_embeddings_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.jobs.schemas.job_batch_schemas import JobBatchResponse

router = APIRouter(prefix="/semantic", tags=["semantic"])


def _batch_to_response(batch: JobBatch) -> JobBatchResponse:
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


@router.post(
    "/backfill",
    response_model=JobBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@require_embeddings_enabled
async def backfill_embeddings(
    current_user: Annotated[User, Depends(get_current_user)],
    book_id: int | None = None,
    use_case: EnqueueContentEmbeddingsUseCase = Depends(
        inject_use_case(container.semantic.enqueue_content_embeddings_use_case)
    ),
) -> JobBatchResponse:
    """Enqueue an embedding batch for the user's content, optionally scoped to a book.

    Poll progress through ``GET /jobs/batches/{id}``.
    """
    batch = await use_case.execute(
        UserId(current_user.id.value),
        BookId(book_id) if book_id is not None else None,
    )
    return _batch_to_response(batch)
