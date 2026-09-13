"""Where a reader last was in a book they are reading in the browser."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.domain.common.aggregate_root import AggregateRoot
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects import (
    BookId,
    ReadingSessionId,
    UserId,
    WebReadingPositionId,
    XPoint,
)
from src.domain.common.value_objects.position import Position


@dataclass
class WebReadingPosition(AggregateRoot[WebReadingPositionId]):
    """One book's last web-reader position, for one reader.

    Not where "how far through the book am I" is answered -- that stays the
    latest reading session's ``end_position`` (ADR-0004, Amendment 3). What
    lives here is the locator a browser can be put back from, the hash of the
    EPUB it was derived against, and the session still being extended.

    The two clocks are the reason there are two timestamps. ``updated_at`` is
    the *server's* and answers which write was last -- it must be a fact about
    this server, or a device with a slow clock is locked out of writing for
    good. ``recorded_at`` is the *reader's* and answers whether the reader has
    moved: a write must beat it to *move* the position. One field cannot do
    both, because a tab idling on page 20 while another advances to page 100
    sends its closing write with a perfectly fresh arrival and an hour-old
    position.
    """

    id: WebReadingPositionId
    user_id: UserId
    book_id: BookId
    locator: Mapping[str, Any]
    xpoint: XPoint
    locator_source_hash: str
    updated_at: datetime
    recorded_at: datetime
    position: Position | None = None
    reading_session_id: ReadingSessionId | None = None

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.locator:
            raise DomainError("A reading position must carry the locator it was made from")

    @classmethod
    def create(
        cls,
        user_id: UserId,
        book_id: BookId,
        locator: Mapping[str, Any],
        xpoint: XPoint,
        locator_source_hash: str,
        written_at: datetime,
        recorded_at: datetime,
        position: Position | None = None,
    ) -> "WebReadingPosition":
        """Describe where a reader is now, for the store to write if it is the latest.

        Built for every write, not only the first: the store keys on the reader
        and the book and decides in one statement whether this observation is
        the newest, so there is nothing for a caller to load, mutate and write
        back -- and nothing for two tabs to race over.
        """
        return cls(
            id=WebReadingPositionId.generate(),
            user_id=user_id,
            book_id=book_id,
            locator=locator,
            xpoint=xpoint,
            locator_source_hash=locator_source_hash,
            updated_at=written_at,
            recorded_at=recorded_at,
            position=position,
        )
