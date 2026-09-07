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
    - Time only moves forward. ``record`` refuses an observation older than the
      one already stored, so a write that arrives late -- the page-unload beacon
      overtaken by an ordinary write -- cannot rewind the reader's place.
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
        observed_at: datetime,
        position: Position | None = None,
        reading_session_id: ReadingSessionId | None = None,
    ) -> "WebReadingPosition":
        """Start recording where a reader is in a book they have not read here before."""
        return cls(
            id=WebReadingPositionId.generate(),
            user_id=user_id,
            book_id=book_id,
            locator=locator,
            xpoint=xpoint,
            updated_at=observed_at,
            position=position,
            reading_session_id=reading_session_id,
        )

    def is_newer_than_stored(self, observed_at: datetime) -> bool:
        """Whether an observation made at ``observed_at`` has anything to add.

        Asked before the work of converting a locator is done, so that a stale
        write is cheap as well as harmless. Equal timestamps count as stale: the
        reader was in one place at one instant, and the copy already stored is
        as good as the one arriving.
        """
        return observed_at > self.updated_at

    def record(
        self,
        locator: Mapping[str, Any],
        xpoint: XPoint,
        observed_at: datetime,
        position: Position | None,
        reading_session_id: ReadingSessionId | None,
    ) -> None:
        """Move the stored position to where the reader now is.

        Raises:
            DomainError: If ``observed_at`` is not after the stored observation.
                The caller is expected to have asked
                :meth:`is_newer_than_stored` first and skipped the write; this
                is the invariant behind that, not a control-flow path.
        """
        if not self.is_newer_than_stored(observed_at):
            raise DomainError("A reading position cannot move backwards in time")
        if not locator:
            raise DomainError("A reading position must carry the locator it was made from")
        self.locator = locator
        self.xpoint = xpoint
        self.updated_at = observed_at
        self.position = position
        self.reading_session_id = reading_session_id

    def close_session(self) -> None:
        """Forget the open reading session, so the next write starts a new one.

        The session itself is untouched. Nothing has to be written to *end* a
        web reading session -- its end time is the last position it was told
        about, so a session ends by simply not being extended again. This only
        decides that the next write will not extend it.
        """
        self.reading_session_id = None
