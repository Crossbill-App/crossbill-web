"""Port for persisting content embeddings.

An embedding row is derived data, not a domain aggregate: the repository works
with a plain ``ContentType`` + ``content_id`` key and raw ints, never a typed
entity id.
"""

from dataclasses import dataclass
from typing import Protocol

from src.application.semantic.content_type import ContentType


@dataclass(frozen=True)
class EmbeddingState:
    """The idempotency spine of a stored embedding.

    An embedding is stale when either the content hash or the model version no
    longer matches the source; comparing this state avoids a needless model call.
    """

    content_hash: str
    model_name: str
    model_version: str


@dataclass(frozen=True)
class EmbeddingWrite:
    """Everything needed to persist one content unit's embedding."""

    content_type: ContentType
    content_id: int
    user_id: int
    book_id: int | None
    embedding: list[float]
    model_name: str
    model_version: str
    content_hash: str


class EmbeddingRepositoryProtocol(Protocol):
    """Upsert-style store for content embeddings."""

    async def upsert(self, record: EmbeddingWrite) -> None:
        """Insert or replace the embedding for a content unit."""
        ...

    async def get_state(self, content_type: ContentType, content_id: int) -> EmbeddingState | None:
        """Return the stored idempotency state, or ``None`` if not embedded yet."""
        ...

    async def delete_for(self, content_type: ContentType, content_ids: list[int]) -> None:
        """Remove the embeddings for units of one type, in one statement.

        Callers must pass ids they have already established the user owns: this
        filters on ``content_type`` and id alone.

        Used by soft-delete paths, which no foreign key can reach -- a soft
        delete is an ``UPDATE`` of ``deleted_at``, so the source row never leaves
        the table and the database has nothing to cascade from -- and by the job
        when a unit's source has gone entirely.
        """
        ...
