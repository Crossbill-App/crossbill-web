"""Read use case for free-text semantic search over content embeddings."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.application.semantic.queries.content_search import (
    SearchHydrationQueryProtocol,
    SemanticSearchResultsView,
    group_by_content_type,
)
from src.application.semantic.queries.semantic_search import (
    SemanticSearchHit,
    SemanticSearchQueryProtocol,
)


class SearchContentUseCase:
    """Embed the query once, rank each content type separately, and hydrate each group."""

    def __init__(
        self,
        query: SemanticSearchQueryProtocol,
        client: EmbeddingClientProtocol,
        hydration: SearchHydrationQueryProtocol,
    ) -> None:
        self.query = query
        self.client = client
        self.hydration = hydration

    async def execute(
        self, *, query_text: str, user_id: int, book_id: int | None, limit: int
    ) -> SemanticSearchResultsView:
        """Return the most similar units of each type, most similar first within each group.

        ``limit`` applies per content type.
        """
        vectors = await self.client.embed([query_text])
        embedding = vectors[0]

        async def scan(content_type: ContentType) -> list[SemanticSearchHit]:
            return await self.query.nearest(
                embedding=embedding,
                user_id=user_id,
                book_id=book_id,
                limit=limit,
                content_type=content_type,
            )

        return await group_by_content_type(scan, self.hydration, user_id)
