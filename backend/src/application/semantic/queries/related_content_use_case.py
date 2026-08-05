"""Read use case for "related content" — nearest neighbours of a given unit."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import ContentSourceProtocol
from src.application.semantic.queries.hydration import hydrate_hits
from src.application.semantic.queries.semantic_search import (
    SemanticSearchQueryProtocol,
    SemanticSearchView,
)


class RelatedContentUseCase:
    """Rank the index against a unit's already-stored vector, excluding the unit itself."""

    def __init__(
        self, query: SemanticSearchQueryProtocol, content_source: ContentSourceProtocol
    ) -> None:
        self.query = query
        self.content_source = content_source

    async def execute(
        self, *, content_type: ContentType, content_id: int, user_id: int, limit: int
    ) -> list[SemanticSearchView]:
        """Return the units most similar to this one, or ``[]`` if it is not indexed."""
        vector = await self.query.get_vector(
            content_type=content_type, content_id=content_id, user_id=user_id
        )
        if vector is None:
            return []
        hits = await self.query.nearest(
            embedding=vector,
            user_id=user_id,
            book_id=None,
            limit=limit,
            exclude=(content_type, content_id),
        )
        return await hydrate_hits(hits, self.content_source)
