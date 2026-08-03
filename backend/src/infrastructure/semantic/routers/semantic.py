"""API router for semantic-search ingestion (backfill)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.application.semantic.commands.enqueue_content_embeddings_use_case import (
    EnqueueContentEmbeddingsUseCase,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.related_content_use_case import RelatedContentUseCase
from src.application.semantic.queries.search_content_use_case import SearchContentUseCase
from src.application.semantic.queries.semantic_search import SemanticSearchView
from src.core import container
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.identity import User
from src.domain.jobs.entities.job_batch import JobBatch
from src.infrastructure.common.dependencies import require_embeddings_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.jobs.schemas.job_batch_schemas import JobBatchResponse
from src.infrastructure.semantic.schemas.semantic_schemas import SemanticSearchResult

router = APIRouter(prefix="/semantic", tags=["semantic"])

MAX_SEARCH_LIMIT = 50


def _result(view: SemanticSearchView) -> SemanticSearchResult:
    return SemanticSearchResult(
        content_type=view.content_type,
        content_id=view.content_id,
        book_id=view.book_id,
        score=view.score,
        text=view.text,
    )


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
    dependencies=[Depends(require_embeddings_enabled)],
)
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


@router.get(
    "/search",
    response_model=list[SemanticSearchResult],
    dependencies=[Depends(require_embeddings_enabled)],
)
async def search_content(
    current_user: Annotated[User, Depends(get_current_user)],
    q: str,
    book_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = 10,
    use_case: SearchContentUseCase = Depends(
        inject_use_case(container.semantic.search_content_use_case)
    ),
) -> list[SemanticSearchResult]:
    """Rank the user's embedded content by semantic similarity to a free-text query."""
    views = await use_case.execute(
        query_text=q,
        user_id=current_user.id.value,
        book_id=book_id,
        limit=limit,
    )
    return [_result(view) for view in views]


@router.get(
    "/related",
    response_model=list[SemanticSearchResult],
    dependencies=[Depends(require_embeddings_enabled)],
)
async def related_content(
    current_user: Annotated[User, Depends(get_current_user)],
    content_type: ContentType,
    content_id: int,
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = 10,
    use_case: RelatedContentUseCase = Depends(
        inject_use_case(container.semantic.related_content_use_case)
    ),
) -> list[SemanticSearchResult]:
    """Rank the user's embedded content by similarity to one already-indexed unit."""
    views = await use_case.execute(
        content_type=content_type,
        content_id=content_id,
        user_id=current_user.id.value,
        limit=limit,
    )
    return [_result(view) for view in views]
