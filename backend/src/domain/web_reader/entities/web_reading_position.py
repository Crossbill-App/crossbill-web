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

    **This is not where "how far through the book am I" is answered.** That
    stays the latest reading session's ``end_position``, as it was before the
    web reader existed, which is why the progress bar and
    ``ReadingStatisticsCalculator`` needed no change to understand browser
    reading (ADR-0004, Amendment 3). What this aggregate holds is the two
    things a reading session cannot:

    1. **The locator**, so the browser can be put back exactly where it was.
       A locator is derived, never canonical (ADR-0004 §2) -- it is stored here
       as the opaque JSON the navigator produced, because the only thing that
       will ever read it is another navigator. If the EPUB is replaced, this
       becomes a locator into a book that no longer exists, and the ``xpoint``
       beside it is what still means something.
    2. **Which reading session is still open**, so that the next position write
       knows whether it is continuing a sitting or starting one.

    Business rules:
    - A stored position always has a canonical ``xpoint``. A locator that could
      not be converted is not a position worth keeping, because nothing but the
      browser could ever read it back.
    - ``position`` may be absent: it is resolved through a ``PositionIndex``
      built from the EPUB, and an xpointer the index does not know resolves to
      nothing. Progress is then unknown rather than zero.
    - ``updated_at`` is the *server's* clock, not the reader's, and it only
      moves forward. It answers "which write was last", which has to be a fact
      about this server: a second device whose clock is five minutes slow would
      otherwise have every write it ever made read as older than what is stored
      and be refused for good. The reader's own clock is used for the reading
      session's arithmetic, where it is the honest source, and nowhere else.
    """

    id: WebReadingPositionId
    user_id: UserId
    book_id: BookId
    locator: Mapping[str, Any]
    xpoint: XPoint
    updated_at: datetime
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
        recorded_at: datetime,
        position: Position | None = None,
        reading_session_id: ReadingSessionId | None = None,
    ) -> "WebReadingPosition":
        """Describe where a reader is now, for the store to write if it is the latest.

        Built for every write, not only the first: the store keys on the reader
        and the book and decides in one statement whether this observation is
        the newest one, so there is nothing for a caller to load, mutate and
        write back -- and nothing for two tabs to race over.
        """
        return cls(
            id=WebReadingPositionId.generate(),
            user_id=user_id,
            book_id=book_id,
            locator=locator,
            xpoint=xpoint,
            updated_at=recorded_at,
            position=position,
            reading_session_id=reading_session_id,
        )

    def close_session(self) -> None:
        """Forget the open reading session, so the next write starts a new one.

        The session itself is untouched. Nothing has to be written to *end* a
        web reading session -- its end time is the last position it was told
        about, so a session ends by simply not being extended again. This only
        decides that the next write will not extend it.
        """
        self.reading_session_id = None
