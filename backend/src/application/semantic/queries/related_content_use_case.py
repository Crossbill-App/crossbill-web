"""Read use case for "related content" — nearest neighbours of a given unit."""

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.content_search import (
    RankedContentGroupsView,
    SearchHydrationQueryProtocol,
    hydrate_by_content_type,
)
from src.application.semantic.queries.ranking import CANDIDATE_FACTOR, related_page
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
    ) -> RankedContentGroupsView:
        """Return the units most similar to this one, grouped by content type.

        Ranks ``CANDIDATE_FACTOR`` times more candidates than asked for, because
        the page is chosen from them rather than being their prefix: the
        cross-book cap in ``ranking`` needs room to reach past a book that has
        already filled its share. A group may come back shorter than ``limit``
        -- the score floor is applied last and nothing backfills below it.
        """
        anchor = await self.query.get_anchor(
            content_type=content_type, content_id=content_id, user_id=user_id
        )
        if anchor is None:
            return RankedContentGroupsView(highlights=(), notes=(), digests=())

        # Bound out here so the group being ranked cannot shadow it: the unit to
        # exclude is the anchor, whatever type the scan is currently over.
        exclude = (content_type, content_id)

        async def scan(group: ContentType) -> list[SemanticSearchHit]:
            return await self.query.nearest(
                embedding=anchor.vector,
                user_id=user_id,
                book_id=None,
                limit=limit * CANDIDATE_FACTOR,
                content_type=group,
                exclude=exclude,
            )

        candidates = {
            ContentType.HIGHLIGHT: await scan(ContentType.HIGHLIGHT),
            ContentType.NOTE: await scan(ContentType.NOTE),
            ContentType.DIGEST: await scan(ContentType.DIGEST),
        }
        page = related_page(candidates, anchor_book_id=anchor.book_id, limit=limit)
        return await hydrate_by_content_type(page, self.hydration, user_id)
