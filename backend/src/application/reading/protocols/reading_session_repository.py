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
