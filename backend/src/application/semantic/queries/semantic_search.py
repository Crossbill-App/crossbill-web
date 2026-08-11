"""Read model for semantic (nearest-neighbour) search over content embeddings.

These are view DTOs and a query port, not domain types: an embedding row is
derived data with no aggregate (ADR-0002). ``score`` is cosine *similarity* --
higher means more similar -- so callers never see raw distances. Its range is
``[-1, 1]``: pgvector's ``<=>`` yields cosine distance in ``[0, 2]`` and the
adapter reports ``1 - distance``. In practice text embeddings cluster well above
zero, but nothing clamps the value, so do not treat it as a ``[0, 1]`` fraction.
"""

from dataclasses import dataclass
from typing import Protocol

from src.application.semantic.content_type import ContentType


@dataclass(frozen=True)
class SemanticSearchHit:
    """One nearest-neighbour match, before its source text is hydrated."""

    content_type: ContentType
    content_id: int
    book_id: int | None
    score: float


class SemanticSearchQueryProtocol(Protocol):
    """Port for the nearest-neighbour scan over the embeddings index."""

    async def nearest(
        self,
        *,
        embedding: list[float],
        user_id: int,
        book_id: int | None,
        limit: int,
        content_type: ContentType | None = None,
        exclude: tuple[ContentType, int] | None = None,
    ) -> list[SemanticSearchHit]:
        """Rank the user's embeddings by similarity to ``embedding``, most similar first.

        ``content_type`` narrows the scan to one kind of unit; ``None`` scans
        every kind. The grouped search runs one scan per type so no type can
        crowd the others out of a single ranked page.
        """
        ...

    async def get_vector(
        self, *, content_type: ContentType, content_id: int, user_id: int
    ) -> list[float] | None:
        """Return the stored vector for a content unit, or ``None`` if it is not indexed."""
        ...
