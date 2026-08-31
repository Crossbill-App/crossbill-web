"""
ReadingSession aggregate root.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.common.aggregate_root import AggregateRoot
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects import (
    BookId,
    ContentHash,
    ReadingSessionId,
    UserId,
    XPointRange,
)
from src.domain.common.value_objects.position import Position


@dataclass
class ReadingSession(AggregateRoot[ReadingSessionId]):
    """
    Reading session aggregate root.

    Represents a continuous reading session recorded by an e-reader.

    Business Rules:
    - Start time must be before end time
    - Duration is computed from start/end times
    - Start page must be <= end page
    - Content hash prevents duplicate sessions
    """

    # Identity
    id: ReadingSessionId
    user_id: UserId
    book_id: BookId

    # Time tracking
    start_time: datetime
    end_time: datetime

    content_hash: ContentHash = field(init=False)

    # Position tracking (optional)
    start_xpoint: XPointRange | None = None
    start_page: int | None = None
    end_page: int | None = None
    start_position: Position | None = None
    end_position: Position | None = None

    # Metadata
    device_id: str | None = None
    created_at: datetime | None = None

    # Related highlights (IDs only - don't load full entities)
    _highlight_ids: list[int] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate invariants."""
        if self.end_time < self.start_time:
            raise DomainError("End time must be after start time")

        if self.start_page is not None and self.end_page is not None:
            if self.end_page < self.start_page:
                raise DomainError("End page must be >= start page")
            if self.start_page < 0 or self.end_page < 0:
                raise DomainError("Page numbers cannot be negative")

        hash_input = f"{self.book_id}|{self.user_id}|{self.start_time}|{self.device_id or ''}"
        self.content_hash = ContentHash.compute(hash_input)

    @classmethod
    def create(
        cls,
        user_id: UserId,
        book_id: BookId,
        start_time: datetime,
        end_time: datetime,
        start_page: int | None = None,
        end_page: int | None = None,
        start_xpoint: XPointRange | None = None,
        start_position: Position | None = None,
        end_position: Position | None = None,
        device_id: str | None = None,
    ) -> "ReadingSession":
        """
        Factory method for creating a new reading session.

        Args:
            user_id: User who read
            book_id: Book that was read
            start_time: Session start time
            end_time: Session end time
            start_page: Optional starting page
            end_page: Optional ending page
            start_xpoint: Optional XPoint range
            start_position: Optional start Position
            end_position: Optional end Position
            device_id: Optional device identifier

        Returns:
            New ReadingSession instance
        """

        return cls(
            id=ReadingSessionId.generate(),
            user_id=user_id,
            book_id=book_id,
            start_time=start_time,
            end_time=end_time,
            start_page=start_page,
            end_page=end_page,
            start_xpoint=start_xpoint,
            start_position=start_position,
            end_position=end_position,
            device_id=device_id,
            _highlight_ids=[],
        )
