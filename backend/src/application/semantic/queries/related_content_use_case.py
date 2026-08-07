"""Read use case for "related content" — nearest neighbours of a given unit."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import (
    ContentSourceProtocol,
    EmbeddableContent,
)
from src.application.semantic.queries.semantic_search import (
    SemanticSearchHit,
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
        return await self._hydrate(hits)

    async def _hydrate(self, hits: list[SemanticSearchHit]) -> list[SemanticSearchView]:
        """Resolve hits' text in ranking order, dropping any whose source is gone.

        Resolution is batched by content type: at most three queries for a page,
        regardless of ``k``, instead of one per hit.

        Dropping an unresolvable hit is what makes "deleted content never
        surfaces" true (ADR-0002's consistency model, rule 2) -- the guarantee
        itself, not a safety net over the cascade anchors, and free because the
        text has to be fetched to render a result anyway. It carries real weight
        for a soft-deleted highlight, whose embedding survives until the next
        backfill sweep because no foreign key can see an UPDATE of
        ``deleted_at``.

        Only /related hydrates this way. ``text`` is the embedding input --
        truncated and lossily concatenated -- so it cannot render a note's title
        as a title. The grouped search resolves display fields through
        ``queries/content_search.py`` instead; /related should follow when it
        grows a UI of its own.
        """
        ids_by_type: dict[ContentType, list[int]] = {}
        for hit in hits:
            ids_by_type.setdefault(hit.content_type, []).append(hit.content_id)

        resolved: dict[tuple[ContentType, int], EmbeddableContent] = {}
        for hit_type, content_ids in ids_by_type.items():
            found = await self.content_source.get_embeddable_many(hit_type, content_ids)
            for content_id, content in found.items():
                resolved[(hit_type, content_id)] = content

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
