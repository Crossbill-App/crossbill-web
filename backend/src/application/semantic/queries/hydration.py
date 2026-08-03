"""Shared text hydration for semantic-search read use cases.

Both the free-text search and the related-content view rank the same index and
then need each hit's source text. That resolution is the one thing they share,
so it lives here rather than in either use case.

Hits whose source row cannot be resolved are dropped. Since the cascade anchors
landed this should be vanishingly rare -- deleting content now takes its
embedding with it -- but the check stays because it costs nothing (the text has
to be fetched to render a result anyway) and it is what guarantees deleted
content never surfaces, rather than making that guarantee depend on a foreign
key having fired and a cleanup having succeeded. The residual cases are the
window between a soft delete and its embedding cleanup, and content deleted
between the ranking query and this one.
"""

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import (
    ContentSourceProtocol,
    EmbeddableContent,
)
from src.application.semantic.queries.semantic_search import (
    SemanticSearchHit,
    SemanticSearchView,
)


async def hydrate_hits(
    hits: list[SemanticSearchHit], content_source: ContentSourceProtocol
) -> list[SemanticSearchView]:
    """Resolve hits' text in ranking order, dropping any whose source is gone.

    Resolution is batched by content type: at most three queries for a page,
    regardless of ``k``, instead of one per hit.
    """
    ids_by_type: dict[ContentType, list[int]] = {}
    for hit in hits:
        ids_by_type.setdefault(hit.content_type, []).append(hit.content_id)

    resolved: dict[tuple[ContentType, int], EmbeddableContent] = {}
    for content_type, content_ids in ids_by_type.items():
        found = await content_source.get_embeddable_many(content_type, content_ids)
        for content_id, content in found.items():
            resolved[(content_type, content_id)] = content

    return [
        SemanticSearchView(
            content_type=hit.content_type,
            content_id=hit.content_id,
            book_id=hit.book_id,
            score=hit.score,
            text=resolved[(hit.content_type, hit.content_id)].text,
        )
        for hit in hits
        if (hit.content_type, hit.content_id) in resolved
    ]
