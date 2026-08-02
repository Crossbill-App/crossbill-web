"""Bookmark entity for saving highlights to a book's navigation index."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.common.entity import Entity
from src.domain.common.value_objects.ids import BookId, BookmarkId, HighlightId


@dataclass
class Bookmark(Entity[BookmarkId]):
    """
    Bookmark that saves a highlight into a book's index of saved highlights.

    A book has many bookmarks; the UI renders them as a jump list for
    navigating back to highlights worth returning to. Bookmarks say nothing
    about reading progress.

    Business Rules:
    - A bookmark links a highlight within a book
    - User ownership is verified through the book relationship
    - One bookmark per highlight (uniqueness enforced at book+highlight level)
    """

    id: BookmarkId
    book_id: BookId
    highlight_id: HighlightId
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate invariants."""
        # No additional validation needed - IDs validated by value objects

    @classmethod
    def create(cls, book_id: BookId, highlight_id: HighlightId) -> "Bookmark":
        """
        Create a new bookmark.

        Args:
            book_id: ID of the book
            highlight_id: ID of the highlight to bookmark

        Returns:
            New Bookmark instance
        """
        return cls(
            id=BookmarkId.generate(),
            book_id=book_id,
            highlight_id=highlight_id,
        )

    @classmethod
    def create_with_id(
        cls,
        id: BookmarkId,
        book_id: BookId,
        highlight_id: HighlightId,
        created_at: datetime,
    ) -> "Bookmark":
        """
        Reconstitute a bookmark from persistence.

        Args:
            id: Existing bookmark ID
            book_id: ID of the book
            highlight_id: ID of the highlight
            created_at: Timestamp when bookmark was created

        Returns:
            Reconstituted Bookmark instance
        """
        return cls(
            id=id,
            book_id=book_id,
            highlight_id=highlight_id,
            created_at=created_at,
        )
