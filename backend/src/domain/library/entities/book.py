import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from src.domain.common.entity import Entity
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position


class ReadingStage(StrEnum):
    """Manual, user-set stage of engagement with a book."""

    TO_READ = "to_read"
    SKIMMING = "skimming"
    READING = "reading"
    FINISHED = "finished"
    REFLECTED = "reflected"
    DID_NOT_FINISH = "did_not_finish"


@dataclass
class Book(Entity[BookId]):
    """
    Book aggregate root.

    Represents a book in a user's library.
    """

    # Identity
    id: BookId
    user_id: UserId

    # Essential metadata
    title: str

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Optional fields
    author: str | None = None
    client_book_id: str | None = None  # From KOReader for deduplication
    isbn: str | None = None
    description: str | None = None
    language: str | None = None
    page_count: int | None = None
    ebook_file: str | None = None
    file_type: str | None = None
    cover_file: str | None = None
    cover_blurhash: str | None = None
    last_viewed: datetime | None = None
    last_synced: datetime | None = None
    end_position: Position | None = None
    reading_stage: ReadingStage | None = None

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.title or not self.title.strip():
            raise DomainError("Book title cannot be empty")

        if self.page_count is not None and self.page_count < 0:
            raise DomainError("Page count cannot be negative")

    # Query methods
    def has_been_viewed(self) -> bool:
        """Check if book has been viewed."""
        return self.last_viewed is not None

    # Command methods
    def mark_as_viewed(self) -> None:
        """Update last viewed timestamp to now."""
        self.last_viewed = datetime.now(UTC)

    def mark_as_synced(self) -> None:
        """Record that a device has just sent this book's data.

        Stamped by the server rather than the device: e-reader clocks drift,
        and a wrong one would pin the book to an end of the recently-synced
        list with no way to correct it.
        """
        self.last_synced = datetime.now(UTC)

    def update_end_position(self, position: Position) -> None:
        """Update the book's end position (total document length)."""
        self.end_position = position

    def set_file(self, file_type: str) -> str:
        """Set ebook file reference, generating a UUID filename on first upload.

        Returns the filename (existing or newly generated).
        """
        if file_type != "epub":
            raise DomainError(f"Invalid file type: {file_type}")
        if self.ebook_file is not None:
            self.file_type = file_type
            return self.ebook_file
        self.ebook_file = f"{uuid.uuid4()}.{file_type}"
        self.file_type = file_type
        return self.ebook_file

    def set_cover_file(self) -> str:
        """Set cover file reference, generating a UUID filename on first upload.

        Returns the filename (existing or newly generated).
        """
        if self.cover_file is not None:
            return self.cover_file
        self.cover_file = f"{uuid.uuid4()}.jpg"
        return self.cover_file

    def set_cover_blurhash(self, blurhash: str) -> None:
        """Set the blurhash string for the cover image."""
        self.cover_blurhash = blurhash

    def set_reading_stage(self, reading_stage: ReadingStage | None) -> None:
        """Set the manual reading stage."""
        self.reading_stage = reading_stage

    def set_description(self, description: str | None) -> None:
        """Set the book's blurb, treating blank text as no blurb at all."""
        stripped = description.strip() if description else ""
        self.description = stripped or None

    # Factory methods
    @classmethod
    def create(
        cls,
        user_id: UserId,
        title: str,
        client_book_id: str | None = None,
        author: str | None = None,
        isbn: str | None = None,
        description: str | None = None,
        language: str | None = None,
        page_count: int | None = None,
        ebook_file: str | None = None,
        file_type: str | None = None,
        cover_file: str | None = None,
        cover_blurhash: str | None = None,
        end_position: Position | None = None,
        reading_stage: ReadingStage | None = None,
    ) -> "Book":
        """Factory for creating new book."""
        now = datetime.now(UTC)
        return cls(
            id=BookId.generate(),
            user_id=user_id,
            title=title.strip(),
            client_book_id=client_book_id,
            author=author.strip() if author else None,
            isbn=isbn,
            description=description,
            language=language,
            page_count=page_count,
            ebook_file=ebook_file,
            file_type=file_type,
            cover_file=cover_file,
            cover_blurhash=cover_blurhash,
            created_at=now,
            updated_at=now,
            last_viewed=None,
            last_synced=None,
            end_position=end_position,
            reading_stage=reading_stage,
        )

    @classmethod
    def create_with_id(
        cls,
        id: BookId,
        user_id: UserId,
        title: str,
        created_at: datetime,
        updated_at: datetime,
        client_book_id: str | None = None,
        author: str | None = None,
        isbn: str | None = None,
        description: str | None = None,
        language: str | None = None,
        page_count: int | None = None,
        ebook_file: str | None = None,
        file_type: str | None = None,
        cover_file: str | None = None,
        cover_blurhash: str | None = None,
        last_viewed: datetime | None = None,
        last_synced: datetime | None = None,
        end_position: Position | None = None,
        reading_stage: ReadingStage | None = None,
    ) -> "Book":
        """Factory for reconstituting book from persistence."""
        return cls(
            id=id,
            user_id=user_id,
            title=title,
            client_book_id=client_book_id,
            author=author,
            isbn=isbn,
            description=description,
            language=language,
            page_count=page_count,
            ebook_file=ebook_file,
            file_type=file_type,
            cover_file=cover_file,
            cover_blurhash=cover_blurhash,
            created_at=created_at,
            updated_at=updated_at,
            last_viewed=last_viewed,
            last_synced=last_synced,
            end_position=end_position,
            reading_stage=reading_stage,
        )
