"""Read use case for free-text semantic search over content embeddings."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.application.semantic.queries.content_search import (
    SearchHydrationQueryProtocol,
    SemanticSearchResultsView,
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

        ``limit`` applies per content type. One scan per type rather than one
        combined scan: a book with thousands of highlights would otherwise fill
        a single ranked page and the digests would never appear.
        """
        vectors = await self.client.embed([query_text])
        embedding = vectors[0]

        async def hits(content_type: ContentType) -> list[SemanticSearchHit]:
            return await self.query.nearest(
                embedding=embedding,
                user_id=user_id,
                book_id=book_id,
                limit=limit,
                content_type=content_type,
            )

        return SemanticSearchResultsView(
            highlights=await self.hydration.highlights(await hits(ContentType.HIGHLIGHT), user_id),
            notes=await self.hydration.notes(await hits(ContentType.NOTE), user_id),
            digests=await self.hydration.digests(await hits(ContentType.DIGEST), user_id),
        )
