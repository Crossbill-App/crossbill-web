"""Read model for semantic (nearest-neighbour) search over content embeddings.

These are view DTOs and a query port, not domain types: an embedding row is
derived data with no aggregate (ADR-0002). ``score`` is cosine similarity in
``[0, 1]`` -- higher means more similar -- so callers never see raw distances.
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


@dataclass(frozen=True)
class SemanticSearchView:
    """A hit with its source text resolved, ready to render."""

    content_type: ContentType
    content_id: int
    book_id: int | None
    score: float
    text: str


class SemanticSearchQueryProtocol(Protocol):
    """Port for the nearest-neighbour scan over the embeddings index."""

    async def nearest(
        self,
        *,
        embedding: list[float],
        user_id: int,
        book_id: int | None,
        limit: int,
        exclude: tuple[ContentType, int] | None = None,
    ) -> list[SemanticSearchHit]:
        """Rank the user's embeddings by similarity to ``embedding``, most similar first."""
        ...

    async def get_vector(
        self, *, content_type: ContentType, content_id: int, user_id: int
    ) -> list[float] | None:
        """Return the stored vector for a content unit, or ``None`` if it is not indexed."""
        ...
