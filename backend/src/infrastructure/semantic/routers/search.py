"""API router for global search -- one query across the whole library.

It sits in the semantic package because it ranks the embeddings index and
shares that index's schemas and bounds, but it answers under ``/search`` rather
than ``/semantic/search``: books are matched by title and author, not by
meaning, so the read as a whole is no longer a semantic one.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.application.semantic.queries.global_search_use_case import GlobalSearchUseCase
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.dependencies import require_embeddings_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.semantic.routers.limits import MAX_SEARCH_ITEMS_PER_TYPE
from src.infrastructure.semantic.schemas.semantic_schemas import GlobalSearchResults

router = APIRouter(tags=["search"])

# Bounded because every query costs a model call: an empty string would buy a
# vector for nothing, and an unbounded one is billed by the token and would
# eventually exceed bge-m3's 8K context.
MAX_QUERY_LENGTH = 1000


@router.get("/search", response_model=GlobalSearchResults)
@require_embeddings_enabled
async def global_search(
    current_user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_LENGTH)],
    book_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_ITEMS_PER_TYPE)] = 10,
    use_case: GlobalSearchUseCase = Depends(
        inject_use_case(container.semantic.global_search_use_case)
    ),
) -> GlobalSearchResults:
    """Search the user's library, grouped by content type.

    Highlights, notes and chapter digests are ranked by semantic similarity to
    the query. ``limit`` applies per group, so no content type can crowd out
    another. Every item in those groups carries its similarity score on one
    scale, and enough identifiers to open the highlight, note or chapter it came
    from.

    Matches below a similarity floor are dropped rather than replaced, so a
    group is short -- or empty -- when the library has nothing to say about the
    query. Nearest-neighbour search would otherwise always answer with its top
    ``limit``, however unrelated.

    Books whose title or author contains the query ride on top of those groups,
    matched by name rather than meaning, unranked and capped at five. A
    ``book_id``-scoped search returns none, which makes that scope a purely
    semantic read of one book's content.
    """
    results = await use_case.execute(
        query_text=q,
        user_id=current_user.id.value,
        book_id=book_id,
        limit=limit,
    )
    return GlobalSearchResults.model_validate(results)
