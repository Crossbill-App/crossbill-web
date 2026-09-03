"""Read use case for free-text semantic search over content embeddings."""

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

#: Books ride alongside three ranked groups, so they get a short fixed cap rather
#: than the caller's per-type ``limit``.
MAX_BOOK_MATCHES = 5


class SearchContentUseCase:
    """Embed the query once, rank each content type separately, and hydrate each group."""

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

        Books matching the query by name ride on top, unranked and capped at
        ``MAX_BOOK_MATCHES``.
        """
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
            books=await self._matching_books(query_text, user_id, book_id),
        )

    async def _matching_books(
        self, query_text: str, user_id: int, book_id: int | None
    ) -> tuple[BookSearchView, ...]:
        """Books whose title or author contains the query, in title order.

        A search already scoped to one book gets none: the reader is inside that
        book and offering it back as a result says nothing.
        """
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
