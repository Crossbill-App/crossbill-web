"""Port for resolving embeddable text across source modules.

The content source is the one place that reaches into other modules' data to
turn a ``(ContentType, content_id)`` key into the text that gets embedded, and
to enumerate which content units still need embedding. It hands back plain
DTOs; callers never see the source ORM.
"""

from dataclasses import dataclass
from typing import Protocol

from src.application.semantic.content_type import ContentType


@dataclass(frozen=True)
class EmbeddableContent:
    """One content unit resolved to the text that should be embedded."""

    content_type: ContentType
    content_id: int
    user_id: int
    book_id: int | None
    text: str
    content_hash: str


@dataclass(frozen=True)
class WorkItem:
    """A content unit that needs (re-)embedding, keyed by type + id."""

    content_type: ContentType
    content_id: int


class ContentSourceProtocol(Protocol):
    """Resolves embeddable text and enumerates units needing embedding."""

    async def get_embeddable(
        self, content_type: ContentType, content_id: int
    ) -> EmbeddableContent | None:
        """Resolve one unit's text, or ``None`` if its source row is gone or soft-deleted."""
        ...

    async def get_embeddable_many(
        self, content_type: ContentType, content_ids: list[int]
    ) -> dict[int, EmbeddableContent]:
        """Resolve many units of one type at once, keyed by id.

        Ids whose source row is gone or soft-deleted are absent from the result
        rather than mapping to ``None``. Search hydration uses this so a page of
        hits costs one query per content type instead of one per hit.
        """
        ...

    async def iter_work_items(self, user_id: int, book_id: int | None) -> list[WorkItem]:
        """List the user's content units the backfill has to act on.

        Everything whose embedding is missing, model-stale or content-stale,
        plus the embeddings a soft-deleted highlight left behind -- those come
        back as work items too, because the job prunes them by resolving no
        source (see ``ContentSource._orphans``).
        """
        ...
