"""Port for the store behind a book's last web-reader position."""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects import BookId, ReadingSessionId, UserId
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition


@dataclass(frozen=True)
class RecordedPosition:
    """A position write that won its race, and what it found already open.

    Attributes:
        position: The position as it is now stored, carrying in
            ``reading_session_id`` the sitting that was open *before* this write
            -- the one this write may be continuing.
        advanced: Whether this write moved the stored position, or only proved
            the reader was still there. ``False`` when what was already stored
            was observed later -- an idle tab's closing write, or a heartbeat
            from a second tab. Such a write still extends and may close the
            sitting; it just must not drag the position backwards.
    """

    position: WebReadingPosition
    advanced: bool


class WebReadingPositionRepositoryProtocol(Protocol):
    """Persistence for :class:`WebReadingPosition`, one row per reader and book."""

    async def find_for_book(self, book_id: BookId, user_id: UserId) -> WebReadingPosition | None:
        """Return where this reader last was in this book, or ``None`` if never here."""
        ...

    async def record(self, position: WebReadingPosition) -> RecordedPosition | None:
        """Store the position if it is the newest one, in one statement.

        One statement rather than a read, a decision and a write: two tabs turn
        pages independently, and a decision taken between two round trips is one
        both writers can take. So both questions the write depends on -- *is
        there a row yet* and *is this newer than what is in it* -- are the
        database's to answer, at the moment of writing. ``updated_at`` decides
        whether the write happens at all; ``recorded_at`` decides whether it
        moves the position, which is what ``advanced`` reports.

        The open-session pointer is deliberately **not** written: it is claimed
        separately by :meth:`attach_session`, once the session it should point
        at exists. That narrows a session row left behind a position write that
        did not happen from every lost race to a crash between two commits.

        Returns:
            What is now stored plus the session that was open before, or ``None``
            when a newer observation is already there and this write changed
            nothing.
        """
        ...

    async def attach_session(
        self, position: WebReadingPosition, session_id: ReadingSessionId | None
    ) -> None:
        """Point the row at the reading session this write belongs to, if still the latest.

        The pointer moves only while ``position.updated_at`` is still the value
        in the row, so a writer overtaken in the meantime leaves it to the writer
        that overtook it: neither a close nor an ordinary write can undo what a
        later one decided. ``None`` closes the session, and the next write starts
        a new one.
        """
        ...
