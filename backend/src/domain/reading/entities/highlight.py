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


def device_clock_now() -> dt_module.datetime:
    """Server time as an offsetless wall clock.

    Stands in for a device timestamp when the e-reader sends none, so the
    substitute has the same shape as the real thing: a wall-clock reading with
    no zone attached.
    """
    return dt_module.datetime.now(UTC).replace(tzinfo=None)


@dataclass
class Highlight(AggregateRoot[HighlightId]):
    """
    Highlight aggregate root.

    Represents a text highlight from an e-reader with optional annotations.

    Business Rules:
    - Cannot have empty text
    - Content hash is computed from text (for deduplication)
    - Soft deletion is supported (deleted_at timestamp)
    - Removal from devices is separate: the highlight stays on the web
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
    # Device-local wall clock with no offset: the e-reader does not send one, so
    # none is invented here. Ordering across timezones is approximate.
    datetime: dt_module.datetime = field(default_factory=device_clock_now)
    koreader_updated_at: dt_module.datetime | None = None  # Last edit on the device
    koreader_note: str | None = None  # Note written on the e-reader; not the Notes module
    origin_device_id: str | None = None  # Device the highlight was uploaded from
    created_at: dt_module.datetime = field(default_factory=lambda: dt_module.datetime.now(UTC))
    updated_at: dt_module.datetime = field(default_factory=lambda: dt_module.datetime.now(UTC))
    deleted_at: dt_module.datetime | None = None
    # Set when the user deleted the highlight on an e-reader: it stays on the web,
    # with its flashcards and bookmarks, but is withheld from every device's pull.
    removed_from_devices_at: dt_module.datetime | None = None

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

    def is_removed_from_devices(self) -> bool:
        """Check if this highlight has been withheld from the e-reader pull."""
        return self.removed_from_devices_at is not None

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

    def remove_from_devices(self) -> None:
        """
        Withhold this highlight from every e-reader, keeping it on the web.

        Raises:
            DomainError: If highlight is already removed from devices
        """
        if self.is_removed_from_devices():
            raise DomainError(f"Highlight {self.id} is already removed from devices")

        self.removed_from_devices_at = dt_module.datetime.now(UTC)

    def restore_to_devices(self) -> None:
        """
        Let this highlight reach e-readers again.

        Raises:
            DomainError: If highlight is not removed from devices
        """
        if not self.is_removed_from_devices():
            raise DomainError(f"Highlight {self.id} is not removed from devices")

        self.removed_from_devices_at = None

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
        device_datetime: dt_module.datetime | None = None,
        koreader_updated_at: dt_module.datetime | None = None,
        koreader_note: str | None = None,
        origin_device_id: str | None = None,
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
            device_datetime: Device-side creation time; server time when absent
            koreader_updated_at: Device-side time of the last edit; None until first edited
            koreader_note: Note attached to the highlight on the e-reader
            origin_device_id: Device the upload batch came from

        Returns:
            New Highlight instance

        Raises:
            ValueError: If text is invalid
        """
        highlight_text = text
        now = dt_module.datetime.now(UTC)
        if device_datetime is None:
            device_datetime = device_clock_now()

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
            datetime=device_datetime,
            koreader_updated_at=koreader_updated_at,
            koreader_note=koreader_note,
            origin_device_id=origin_device_id,
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
        device_datetime: dt_module.datetime,
        created_at: dt_module.datetime,
        updated_at: dt_module.datetime,
        chapter_id: ChapterId | None = None,
        xpoints: XPointRange | None = None,
        page: int | None = None,
        position: Position | None = None,
        highlight_style_id: HighlightStyleId | None = None,
        deleted_at: dt_module.datetime | None = None,
        removed_from_devices_at: dt_module.datetime | None = None,
        koreader_updated_at: dt_module.datetime | None = None,
        koreader_note: str | None = None,
        origin_device_id: str | None = None,
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
            datetime=device_datetime,
            koreader_updated_at=koreader_updated_at,
            koreader_note=koreader_note,
            origin_device_id=origin_device_id,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            removed_from_devices_at=removed_from_devices_at,
            _tag_ids=[],
        )
