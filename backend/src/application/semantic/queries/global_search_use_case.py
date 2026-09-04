"""Read use case for global search: ranked content plus books matched by name."""

from src.application.library.queries.book_list import BookListQueryProtocol
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_client import EmbeddingClientProtocol
from src.application.semantic.queries.content_search import (
    BookSearchView,
    GlobalSearchResultsView,
    SearchHydrationQueryProtocol,
    group_by_content_type,
)
from src.application.semantic.queries.ranking import SEARCH_SCORE_FLOOR, above_floor
from src.application.semantic.queries.semantic_search import (
    SemanticSearchHit,
    SemanticSearchQueryProtocol,
)
from src.domain.common.value_objects.ids import UserId
from src.feature_flags import is_embeddings_enabled

#: Fixed, not the caller's per-type ``limit``: books sit above the ranked groups.
MAX_BOOK_MATCHES = 5


class GlobalSearchUseCase:
    """Embed the query once, rank each content type separately, and match books by name."""

    def __init__(
        self,
        query: SemanticSearchQueryProtocol,
        client: EmbeddingClientProtocol,
        hydration: SearchHydrationQueryProtocol,
        books: BookListQueryProtocol,
    ) -> None:
        self.query = query
        self.client = client
        self.hydration = hydration
        self.books = books

    async def execute(
        self, *, query_text: str, user_id: int, book_id: int | None, limit: int
    ) -> GlobalSearchResultsView:
        """Return the most similar units of each type, most similar first within each group.

        ``limit`` applies per content type, and a group can come back shorter:
        weak matches are dropped rather than replaced, so a query with nothing
        to match answers with empty groups instead of the least-bad rows.

        Matching books needs no vectors, so a server without an embedding
        provider still answers -- with that group alone.
        """
        books = await self._matching_books(query_text, user_id, book_id)
        if not is_embeddings_enabled():
            return GlobalSearchResultsView(highlights=(), notes=(), digests=(), books=books)

        vectors = await self.client.embed([query_text])
        embedding = vectors[0]

        async def scan(content_type: ContentType) -> list[SemanticSearchHit]:
            hits = await self.query.nearest(
                embedding=embedding,
                user_id=user_id,
                book_id=book_id,
                limit=limit,
                content_type=content_type,
            )
            return above_floor(hits, SEARCH_SCORE_FLOOR)

        ranked = await group_by_content_type(scan, self.hydration, user_id)
        return GlobalSearchResultsView(
            highlights=ranked.highlights,
            notes=ranked.notes,
            digests=ranked.digests,
            books=books,
        )

    async def _matching_books(
        self, query_text: str, user_id: int, book_id: int | None
    ) -> tuple[BookSearchView, ...]:
        """Books matched by title or author; none for a search already scoped to one book."""
        if book_id is not None:
            return ()

        page = await self.books.list_books(
            user_id=UserId(user_id),
            offset=0,
            limit=MAX_BOOK_MATCHES,
            include_only_with_flashcards=False,
            search_text=query_text,
        )
        return tuple(
            BookSearchView(
                id=book.id,
                title=book.title,
                author=book.author,
                cover_file=book.cover_file,
                cover_blurhash=book.cover_blurhash,
            )
            for book in page.books
        )
