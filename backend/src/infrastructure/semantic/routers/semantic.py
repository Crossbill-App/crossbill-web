"""API router for the semantic slice: embedding ingestion (backfill) and related content.

Free-text search over the same index answers under ``/search`` -- see
``routers/search.py``, which is no longer a semantic-only read.
"""

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
from src.infrastructure.semantic.routers.limits import MAX_SEARCH_ITEMS_PER_TYPE
from src.infrastructure.semantic.schemas.semantic_schemas import (
    BackfillResponse,
    RankedContentGroups,
)

router = APIRouter(prefix="/semantic", tags=["semantic"])


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


@router.get("/related", response_model=RankedContentGroups)
@require_embeddings_enabled
async def related_content(
    current_user: Annotated[User, Depends(get_current_user)],
    content_type: ContentType,
    content_id: int,
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_ITEMS_PER_TYPE)] = 10,
    use_case: RelatedContentUseCase = Depends(
        inject_use_case(container.semantic.related_content_use_case)
    ),
) -> RankedContentGroups:
    """Rank the user's embedded content by similarity to one already-indexed unit.

    The ranked half of ``GET /search``'s body -- the same groups, with ``limit``
    applied per group, so one view can render either; only the unranked ``books``
    of a global search are missing. The anchor is never among its own results,
    and every group is empty when the anchor is not indexed.

    Held to a higher similarity floor than global search: nobody asked for this
    list, so a weak row costs more than a missing one. When the anchor's
    neighbourhood genuinely spans the library, no single book may take more than
    two places in a group, which spreads the page instead of returning one
    book's chapter-by-chapter neighbours. An anchor whose only real neighbours
    are in its own book keeps them.
    """
    results = await use_case.execute(
        content_type=content_type,
        content_id=content_id,
        user_id=current_user.id.value,
        limit=limit,
    )
    return RankedContentGroups.model_validate(results)
