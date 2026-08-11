"""Read use case for "related content" — nearest neighbours of a given unit."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.content_search import (
    SearchHydrationQueryProtocol,
    SemanticSearchResultsView,
    group_by_content_type,
)
from src.application.semantic.queries.semantic_search import (
    SemanticSearchHit,
    SemanticSearchQueryProtocol,
)


class RelatedContentUseCase:
    """Rank the index against a unit's already-stored vector, excluding the unit itself."""

    def __init__(
        self,
        query: SemanticSearchQueryProtocol,
        hydration: SearchHydrationQueryProtocol,
    ) -> None:
        self.query = query
        self.hydration = hydration

    async def execute(
        self, *, content_type: ContentType, content_id: int, user_id: int, limit: int
    ) -> SemanticSearchResultsView:
        """Return the units most similar to this one, grouped by content type."""
        vector = await self.query.get_vector(
            content_type=content_type, content_id=content_id, user_id=user_id
        )
        if vector is None:
            return SemanticSearchResultsView(highlights=(), notes=(), digests=())

        # Bound out here so the group being ranked cannot shadow it: the unit to
        # exclude is the anchor, whatever type the scan is currently over.
        anchor = (content_type, content_id)

        async def scan(group: ContentType) -> list[SemanticSearchHit]:
            return await self.query.nearest(
                embedding=vector,
                user_id=user_id,
                book_id=None,
                limit=limit,
                content_type=group,
                exclude=anchor,
            )

        return await group_by_content_type(scan, self.hydration, user_id)
