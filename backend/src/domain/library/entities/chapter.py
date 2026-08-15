from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.common.entity import Entity
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, ChapterId
from src.domain.common.value_objects.position import Position


@dataclass(frozen=True)
class TocChapter:
    """A chapter entry parsed from an EPUB Table of Contents.

    Parent relationships are expressed by name since DB IDs aren't assigned yet
    during parsing. Names repeat within a TOC, so `parent_index` -- the position
    of the parent entry in the same flattened TOC list, None for roots -- is the
    unambiguous link; `parent_name` remains for callers that have no index.
    """

    name: str
    chapter_number: int
    parent_name: str | None
    start_xpoint: str | None
    end_xpoint: str | None
    start_position: Position | None = None
    end_position: Position | None = None
    parent_index: int | None = None


@dataclass
class Chapter(Entity[ChapterId]):
    """
    Chapter entity.

    Represents a chapter/section in a book's table of contents.
    Supports hierarchical structure via parent_id.
    """

    # Identity
    id: ChapterId
    book_id: BookId

    # Content
    name: str

    # Timestamps
    created_at: datetime

    # Optional fields
    parent_id: ChapterId | None = None
    chapter_number: int | None = None
    start_xpoint: str | None = None
    end_xpoint: str | None = None
    start_position: Position | None = None
    end_position: Position | None = None

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.name or not self.name.strip():
            raise DomainError("Chapter name cannot be empty")

        if self.chapter_number is not None and self.chapter_number < 0:
            raise DomainError("Chapter number cannot be negative")

    # Factory methods
    @classmethod
    def create(
        cls,
        book_id: BookId,
        name: str,
        chapter_number: int | None = None,
        parent_id: ChapterId | None = None,
        start_xpoint: str | None = None,
        end_xpoint: str | None = None,
        start_position: Position | None = None,
        end_position: Position | None = None,
    ) -> "Chapter":
        """Factory for creating new chapter."""
        return cls(
            id=ChapterId.generate(),
            book_id=book_id,
            parent_id=parent_id,
            name=name.strip(),
            chapter_number=chapter_number,
            start_xpoint=start_xpoint,
            end_xpoint=end_xpoint,
            start_position=start_position,
            end_position=end_position,
            created_at=datetime.now(UTC),
        )

    @classmethod
    def create_with_id(
        cls,
        id: ChapterId,
        book_id: BookId,
        name: str,
        created_at: datetime,
        chapter_number: int | None = None,
        parent_id: ChapterId | None = None,
        start_xpoint: str | None = None,
        end_xpoint: str | None = None,
        start_position: Position | None = None,
        end_position: Position | None = None,
    ) -> "Chapter":
        """Factory for reconstituting chapter from persistence."""
        return cls(
            id=id,
            book_id=book_id,
            parent_id=parent_id,
            name=name,
            chapter_number=chapter_number,
            start_xpoint=start_xpoint,
            end_xpoint=end_xpoint,
            start_position=start_position,
            end_position=end_position,
            created_at=created_at,
        )
