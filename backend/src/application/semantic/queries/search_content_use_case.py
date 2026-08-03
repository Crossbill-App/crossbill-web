"""Read use case for free-text semantic search over content embeddings."""

from src.application.semantic.protocols.content_source import ContentSourceProtocol
from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.application.semantic.queries.hydration import hydrate_hits, overfetch_limit
from src.application.semantic.queries.semantic_search import (
    SemanticSearchQueryProtocol,
    SemanticSearchView,
)


class SearchContentUseCase:
    """Embed the query text, rank the index against it, and hydrate the matches."""

    def __init__(
        self,
        query: SemanticSearchQueryProtocol,
        client: EmbeddingClientProtocol,
        content_source: ContentSourceProtocol,
    ) -> None:
        self.query = query
        self.client = client
        self.content_source = content_source

    async def execute(
        self, *, query_text: str, user_id: int, book_id: int | None, limit: int
    ) -> list[SemanticSearchView]:
        """Return the most similar content units, most similar first."""
        vectors = await self.client.embed([query_text])
        hits = await self.query.nearest(
            embedding=vectors[0], user_id=user_id, book_id=book_id, limit=overfetch_limit(limit)
        )
        return await hydrate_hits(hits, self.content_source, limit)
