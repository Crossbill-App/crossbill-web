"""Shared text hydration for semantic-search read use cases.

Both the free-text search and the related-content view rank the same index and
then need each hit's source text. That resolution is the one thing they share,
so it lives here rather than in either use case.

Hits whose source row cannot be resolved are dropped, and that check is what
makes "deleted content never surfaces" true (ADR-0002's consistency model, rule
2). It is not a safety net over the cascade anchors -- it is the guarantee
itself, held here rather than made contingent on a foreign key having fired.
It costs nothing: the text has to be fetched to render a result anyway.

It carries real weight for soft deletes in particular. A soft-deleted highlight
keeps its embedding until the next backfill sweep, because no foreign key can
see an UPDATE of ``deleted_at`` and nothing prunes it at the delete site. This
is what keeps it out of results in the meantime.
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

    # TODO(#543): ``text`` is the embedding input, not a display field -- it is
    # truncated and lossily concatenated, so a note cannot render its title as a
    # title. Hydrate through the modules' own read models instead.
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
