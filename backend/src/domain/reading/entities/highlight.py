"""
Highlight aggregate root.

Encapsulates all business rules for managing highlights.
"""

from __future__ import annotations

import datetime as dt_module
from dataclasses import dataclass, field
from datetime import UTC

from src.domain.common.aggregate_root import AggregateRoot
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    ContentHash,
    HighlightId,
    HighlightStyleId,
    TagId,
    UserId,
    XPointRange,
)
from src.domain.common.value_objects.position import Position


@dataclass
class Highlight(AggregateRoot[HighlightId]):
    """
    Highlight aggregate root.

    Represents a text highlight from an e-reader with optional annotations.

    Business Rules:
    - Cannot have empty text
    - Content hash is computed from text (for deduplication)
    - Soft deletion is supported (deleted_at timestamp)
    - Tags can be added/removed
    """

    # Identity
    id: HighlightId
    user_id: UserId
    book_id: BookId

    # Content
    text: str
    content_hash: ContentHash = field(init=False)

    # Position (optional - may not always be available from e-reader)
    chapter_id: ChapterId | None = None
    xpoints: XPointRange | None = None
    page: int | None = None
    position: Position | None = None

    # Style
    highlight_style_id: HighlightStyleId | None = None

    # Metadata
    datetime: str = ""  # KOReader datetime string
    created_at: dt_module.datetime = field(default_factory=lambda: dt_module.datetime.now(UTC))
    updated_at: dt_module.datetime = field(default_factory=lambda: dt_module.datetime.now(UTC))
    deleted_at: dt_module.datetime | None = None

    # Relationships
    _tag_ids: list[int] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if self.page is not None and self.page < 0:
            raise DomainError("Page number cannot be negative")

        self.content_hash = ContentHash.compute(self.text)

    # Query methods

    def is_deleted(self) -> bool:
        """Check if this highlight has been soft-deleted."""
        return self.deleted_at is not None

    def has_position_info(self) -> bool:
        """Check if this highlight has position information (xpoints or page)."""
        return self.xpoints is not None or self.page is not None

    # Command methods (state changes)

    def soft_delete(self) -> None:
        """
        Soft delete this highlight.

        Raises:
            DomainError: If highlight is already deleted
        """
        if self.is_deleted():
            raise DomainError(f"Highlight {self.id} is already deleted")

        self.deleted_at = dt_module.datetime.now(UTC)

    def restore(self) -> None:
        """
        Restore a soft-deleted highlight.

        Raises:
            DomainError: If highlight is not deleted
        """
        if not self.is_deleted():
            raise DomainError(f"Highlight {self.id} is not deleted")

        self.deleted_at = None

    def associate_with_chapter(self, chapter_id: ChapterId) -> None:
        """Associate this highlight with a chapter."""
        self.chapter_id = chapter_id

    def add_tag(self, tag_id: TagId, tag_book_id: BookId) -> None:
        """
        Add a tag to this highlight (domain validation).

        Tags are owned by the tagging module; a highlight knows only their
        identity and the book they belong to.

        Args:
            tag_id: ID of the tag to add
            tag_book_id: ID of the book the tag belongs to

        Raises:
            DomainError: If tag doesn't belong to same book as highlight
        """
        if tag_book_id != self.book_id:
            raise DomainError(
                f"Tag {tag_id.value} does not belong to the same book as highlight {self.id.value}"
            )

        # Actual persistence of association happens in infrastructure layer
        # This method provides domain-level validation

    @classmethod
    def create(
        cls,
        user_id: UserId,
        book_id: BookId,
        text: str,
        chapter_id: ChapterId | None = None,
        xpoints: XPointRange | None = None,
        page: int | None = None,
        position: Position | None = None,
        highlight_style_id: HighlightStyleId | None = None,
    ) -> Highlight:
        """
        Factory method for creating a new highlight.

        Args:
            user_id: User who created the highlight
            book_id: Book this highlight belongs to
            text: Highlighted text
            chapter_id: Optional chapter reference
            xpoints: Optional XPoint range for precise position
            page: Optional page number
            position: Optional Position for document-order location

        Returns:
            New Highlight instance

        Raises:
            ValueError: If text is invalid
        """
        highlight_text = text
        now = dt_module.datetime.now(UTC)
        datetime_str = now.strftime("%Y-%m-%d %H:%M:%S")

        return cls(
            id=HighlightId.generate(),  # Generate new ID
            user_id=user_id,
            book_id=book_id,
            text=highlight_text,
            chapter_id=chapter_id,
            xpoints=xpoints,
            page=page,
            position=position,
            highlight_style_id=highlight_style_id,
            datetime=datetime_str,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            _tag_ids=[],
        )

    @classmethod
    def create_with_id(
        cls,
        id: HighlightId,
        user_id: UserId,
        book_id: BookId,
        text: str,
        datetime_str: str,
        created_at: dt_module.datetime,
        updated_at: dt_module.datetime,
        chapter_id: ChapterId | None = None,
        xpoints: XPointRange | None = None,
        page: int | None = None,
        position: Position | None = None,
        highlight_style_id: HighlightStyleId | None = None,
        deleted_at: dt_module.datetime | None = None,
    ) -> Highlight:
        """
        Factory method for reconstituting highlight from persistence.

        Used by repositories when loading from database.
        """
        return cls(
            id=id,
            user_id=user_id,
            book_id=book_id,
            text=text,
            chapter_id=chapter_id,
            xpoints=xpoints,
            page=page,
            position=position,
            highlight_style_id=highlight_style_id,
            datetime=datetime_str,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            _tag_ids=[],
        )
