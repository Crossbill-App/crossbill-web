"""API router for job batch management."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.jobs.commands.cancel_job_batch_use_case import CancelJobBatchUseCase
from src.application.jobs.commands.enqueue_book_digests_use_case import (
    EnqueueBookDigestsUseCase,
)
from src.application.jobs.queries.get_active_book_batch_use_case import (
    GetActiveBookBatchUseCase,
)
from src.application.jobs.queries.get_job_batch_use_case import GetJobBatchUseCase
from src.application.jobs.queries.job_batch import JobBatchView
from src.core import container
from src.domain.common.value_objects.ids import BookId, JobBatchId, UserId
from src.domain.identity import User
from src.domain.jobs.entities.job_batch import JobBatch, JobBatchType
from src.infrastructure.common.dependencies import require_ai_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.jobs.schemas.job_batch_schemas import JobBatchResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


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


def _view_to_response(view: JobBatchView) -> JobBatchResponse:
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


@router.post(
    "/books/{book_id}/digest",
    response_model=JobBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@require_ai_enabled
async def enqueue_book_digest(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: EnqueueBookDigestsUseCase = Depends(
        inject_use_case(container.jobs.enqueue_book_digests_use_case)
    ),
) -> JobBatchResponse:
    """Enqueue digest generation for all chapters of a book."""
    batch = await use_case.execute(
        BookId(book_id),
        UserId(current_user.id.value),
    )
    return _batch_to_response(batch)


@router.get(
    "/books/{book_id}/digest",
    response_model=JobBatchResponse | None,
    status_code=status.HTTP_200_OK,
)
async def get_active_book_digest_batch(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetActiveBookBatchUseCase = Depends(
        inject_use_case(container.jobs.get_active_book_batch_use_case)
    ),
) -> JobBatchResponse | None:
    """Get the active digest batch for a book, if any."""
    view = await use_case.execute(
        BookId(book_id),
        UserId(current_user.id.value),
        JobBatchType.CHAPTER_DIGEST,
    )
    return _view_to_response(view) if view else None


@router.get(
    "/batches/{batch_id}",
    response_model=JobBatchResponse,
    status_code=status.HTTP_200_OK,
)
async def get_job_batch(
    batch_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetJobBatchUseCase = Depends(inject_use_case(container.jobs.get_job_batch_use_case)),
) -> JobBatchResponse:
    """Get job batch status."""
    view = await use_case.execute(
        JobBatchId(batch_id),
        UserId(current_user.id.value),
    )
    return _view_to_response(view)


@router.delete(
    "/batches/{batch_id}",
    response_model=JobBatchResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_job_batch(
    batch_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CancelJobBatchUseCase = Depends(
        inject_use_case(container.jobs.cancel_job_batch_use_case)
    ),
) -> JobBatchResponse:
    """Cancel a job batch and abort all pending/active jobs."""
    batch = await use_case.execute(
        JobBatchId(batch_id),
        UserId(current_user.id.value),
    )
    return _batch_to_response(batch)
