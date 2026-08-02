"""Content types embeddable for semantic search.

Shared across all layers: the polymorphic ``embeddings`` table keys rows by
``content_type`` + ``content_id``, and each value names a source module's unit.
"""

from enum import StrEnum


class ContentType(StrEnum):
    """A kind of natural-language unit that can be embedded."""

    NOTE = "note"
    HIGHLIGHT = "highlight"
    DIGEST = "digest"
