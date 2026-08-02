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


async def hydrate_hits(
    hits: list[SemanticSearchHit], content_source: ContentSourceProtocol
) -> list[SemanticSearchView]:
    """Resolve each hit's text in ranking order, skipping hits whose source is gone."""
    views: list[SemanticSearchView] = []
    for hit in hits:
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
