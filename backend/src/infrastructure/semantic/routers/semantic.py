"""API router for semantic search: ingestion (backfill) and the read side."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from starlette import status

from src.application.jobs.queries.get_active_user_batch_use_case import (
    GetActiveUserBatchUseCase,
)
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
from src.domain.jobs.entities.job_batch import JobBatchType
from src.infrastructure.common.dependencies import require_embeddings_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.jobs.schemas.job_batch_schemas import (
    JobBatchResponse,
    batch_to_response,
    view_to_response,
)
from src.infrastructure.semantic.schemas.semantic_schemas import (
    BackfillResponse,
    SemanticSearchResult,
)

router = APIRouter(prefix="/semantic", tags=["semantic"])

MAX_SEARCH_LIMIT = 50
# Bounded because every query costs a model call: an empty string would buy a
# vector for nothing, and an unbounded one is billed by the token and would
# eventually exceed bge-m3's 8K context.
MAX_QUERY_LENGTH = 1000


def _result(view: SemanticSearchView) -> SemanticSearchResult:
    return SemanticSearchResult(
        content_type=view.content_type,
        content_id=view.content_id,
        book_id=view.book_id,
        score=view.score,
        text=view.text,
    )


@router.post(
    "/backfill",
    response_model=BackfillResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_200_OK: {
            "description": "Everything was already indexed; no batch was created",
            # Same body as the 202, or the spec describes 200 as empty and a
            # generated client has nothing to read total_jobs from.
            "model": BackfillResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "A backfill is already running; cancel it or wait",
        },
    },
)
@require_embeddings_enabled
async def backfill_embeddings(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    book_id: int | None = None,
    use_case: EnqueueContentEmbeddingsUseCase = Depends(
        inject_use_case(container.semantic.enqueue_content_embeddings_use_case)
    ),
) -> BackfillResponse:
    """Enqueue an embedding batch for the user's content, optionally scoped to a book.

    Answers 202 with the batch to poll through ``GET /jobs/batches/{id}``, or 200
    with ``total_jobs`` 0 when everything is already indexed. The second is a
    normal outcome of pressing backfill twice, which is why it is not a 4xx: a
    caller cannot tell a rejected request from a satisfied one.

    409 when a backfill is already running -- ``GET /semantic/backfill/active``
    names it, and cancelling it clears the way.
    """
    batch = await use_case.execute(
        UserId(current_user.id.value),
        BookId(book_id) if book_id is not None else None,
    )
    if batch is None:
        # 200, not the route's default 202: nothing was accepted for processing.
        response.status_code = status.HTTP_200_OK
        return BackfillResponse(total_jobs=0, batch=None)
    return BackfillResponse(total_jobs=batch.total_jobs, batch=batch_to_response(batch))


@router.get(
    "/backfill/active",
    response_model=JobBatchResponse | None,
    status_code=status.HTTP_200_OK,
)
@require_embeddings_enabled
async def get_active_backfill(
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetActiveUserBatchUseCase = Depends(
        inject_use_case(container.jobs.get_active_user_batch_use_case)
    ),
) -> JobBatchResponse | None:
    """Get the user's running backfill, if any -- what a 409 from POST refers to."""
    view = await use_case.execute(
        UserId(current_user.id.value),
        JobBatchType.CONTENT_EMBEDDING_BACKFILL,
    )
    return view_to_response(view) if view else None


@router.get("/search", response_model=list[SemanticSearchResult])
@require_embeddings_enabled
async def search_content(
    current_user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_LENGTH)],
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


@router.get("/related", response_model=list[SemanticSearchResult])
@require_embeddings_enabled
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
