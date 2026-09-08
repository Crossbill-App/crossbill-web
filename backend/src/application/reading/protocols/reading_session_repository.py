from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, HighlightId, ReadingSessionId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.reading import ReadingSession


@dataclass
class BulkCreateResult:
    """Result of bulk create operation for reading sessions."""

    created_count: int
    created_sessions: list[ReadingSession]


class ReadingSessionRepositoryProtocol(Protocol):
    async def bulk_create(
        self, user_id: UserId, sessions: list[ReadingSession]
    ) -> BulkCreateResult: ...
    async def find_by_book_id(
        self, book_id: BookId, user_id: UserId, limit: int, offset: int
    ) -> list[ReadingSession]: ...

    async def find_by_id(
        self, session_id: ReadingSessionId, user_id: UserId
    ) -> ReadingSession | None:
        """Return one of the user's sessions, or ``None`` if they have no such session."""
        ...

    async def find_latest_ended(
        self, book_id: BookId, user_id: UserId, excluding_device_id: str | None = None
    ) -> ReadingSession | None:
        """Return the session of this book that ended most recently, or ``None``.

        Ordered by ``end_time`` rather than ``start_time``, because the caller is
        asking where the reader most recently *was*, and a long sitting that
        began before a short later one still ended after it began.

        ``excluding_device_id`` leaves out the sessions one device wrote. The
        rule for which device that is belongs to the caller, not here: this only
        offers the filter.
        """
        ...

    async def save(self, session: ReadingSession) -> ReadingSession:
        """Insert a session, or update the one it already is.

        For the reader that reports its position as it goes rather than
        uploading finished sittings: one session is written when the reading
        starts and rewritten as it goes on.
        """
        ...

    async def bulk_update_positions(
        self,
        position_updates: list[tuple[ReadingSessionId, Position, Position]],
    ) -> int: ...

    async def link_highlights_to_sessions(
        self,
        session_highlight_pairs: list[tuple[ReadingSessionId, HighlightId]],
    ) -> int: ...
