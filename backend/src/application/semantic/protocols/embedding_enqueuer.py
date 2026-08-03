"""Port for enqueuing embedding jobs from source-module write use cases.

This is the one seam source modules (notes, reading) depend on to trigger
embedding. It no-ops when embeddings are disabled and never raises into the
calling write path — a failure to enqueue must not fail a note save or a
highlight upload.
"""

from typing import Protocol

from src.application.semantic.content_type import ContentType


class EmbeddingEnqueuerProtocol(Protocol):
    """Enqueues embedding jobs for content units."""

    async def enqueue_for(self, content_type: ContentType, content_id: int, user_id: int) -> None:
        """Enqueue a single content unit for (re-)embedding."""
        ...

    async def enqueue_many(
        self,
        content_type: ContentType,
        content_ids: list[int],
        user_id: int,
        reference_id: str,
    ) -> None:
        """Enqueue a batch of content units for (re-)embedding."""
        ...
