"""Port for the store behind a book's last web-reader position."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.common.value_objects import BookId, ReadingSessionId, UserId
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition


@dataclass(frozen=True)
class RecordedPosition:
    """A position write that won its race, and what it found already open.

    Attributes:
        position: The position as it is now stored.
        was_open: The reading session the row pointed at *before* this write --
            the sitting this one may be continuing. ``None`` when the reader has
            never read this book here, or closed it last time.
        advanced: Whether this write actually moved the stored position, or only
            proved the reader was still there. ``False`` when what was already
            stored was observed later -- an idle tab's closing write, or a
            heartbeat from a second tab. Such a write still extends and may
            close the sitting; it just must not drag the position backwards.
    """

    position: WebReadingPosition
    was_open: ReadingSessionId | None
    advanced: bool


class WebReadingPositionRepositoryProtocol(Protocol):
    """Persistence for :class:`WebReadingPosition`, one row per reader and book."""

    async def find_for_book(self, book_id: BookId, user_id: UserId) -> WebReadingPosition | None:
        """Return where this reader last was in this book, or ``None`` if never here."""
        ...

    async def record(self, position: WebReadingPosition) -> RecordedPosition | None:
        """Store the position if it is the newest one, in one statement.

        One statement rather than a read, a decision and a write: two tabs turn
        pages independently, and a decision taken in between two round trips is
        one two writers can both take. So both questions the write depends on --
        *is there a row yet* and *is this newer than what is in it* -- are the
        database's to answer, at the moment of writing.

        Two questions, settled in that one statement and reported apart:
        ``position.updated_at`` (the server's clock) decides whether the write
        happens at all, and ``position.recorded_at`` (the reader's) decides
        whether it moves the position -- see ``advanced``.

        The open-session pointer is deliberately **not** written: it is claimed
        separately by :meth:`attach_session`, once the session it should point
        at exists. Nothing may leave a session row behind a position write that
        did not happen.

        Returns:
            What is now stored plus the session that was open before, or
            ``None`` when a newer observation is already there and this write
            changed nothing.
        """
        ...

    async def attach_session(
        self,
        position: WebReadingPosition,
        session_id: ReadingSessionId | None,
        recorded_at: datetime,
    ) -> None:
        """Point the row at the reading session this write belongs to, if still the latest.

        ``recorded_at`` is the ``updated_at`` the caller's own :meth:`record`
        wrote. The pointer moves only while it is still the value in the row --
        so a writer overtaken in the meantime leaves the pointer to the writer
        that overtook it, and neither a close nor an ordinary write can undo
        what a later one decided.

        ``None`` closes the session: the next write starts a new one.
        """
        ...
