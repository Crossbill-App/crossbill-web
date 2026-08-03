"""Shared text hydration for semantic-search read use cases.

Both the free-text search and the related-content view rank the same index and
then need each hit's source text, dropping any hit whose source row has since
been deleted (``get_embeddable`` returns ``None``). That loop is the one thing
they share, so it lives here rather than in either use case.
"""

from src.application.semantic.protocols.content_source import ContentSourceProtocol
from src.application.semantic.queries.semantic_search import (
    SemanticSearchHit,
    SemanticSearchView,
)

#: How many extra candidates to ask the index for, so hits dropped during
#: hydration do not shrink the page below the caller's limit.
_OVERFETCH_FACTOR = 3
_MAX_OVERFETCH = 200


def overfetch_limit(limit: int) -> int:
    """Widen a caller's limit into the number of candidates to rank.

    Hydration drops hits whose source row is gone, and the index cannot filter
    those out (it stores no source state). Ranking only ``limit`` rows would
    therefore return fewer than ``limit`` results whenever a deleted unit is
    still indexed. Over-fetching makes that rare; backfill's orphan pruning is
    what actually keeps the index clean.
    """
    return min(limit * _OVERFETCH_FACTOR, _MAX_OVERFETCH)


async def hydrate_hits(
    hits: list[SemanticSearchHit], content_source: ContentSourceProtocol, limit: int
) -> list[SemanticSearchView]:
    """Resolve hits' text in ranking order, skipping dead sources, capped at ``limit``."""
    views: list[SemanticSearchView] = []
    for hit in hits:
        if len(views) == limit:
            break
        content = await content_source.get_embeddable(hit.content_type, hit.content_id)
        if content is None:
            continue
        views.append(
            SemanticSearchView(
                content_type=hit.content_type,
                content_id=hit.content_id,
                book_id=hit.book_id,
                score=hit.score,
                text=content.text,
            )
        )
    return views
