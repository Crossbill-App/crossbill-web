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
    ) -> ReadingSession | None: ...

    async def bulk_update_positions(
        self,
        position_updates: list[tuple[ReadingSessionId, Position, Position]],
    ) -> int: ...

    async def link_highlights_to_sessions(
        self,
        session_highlight_pairs: list[tuple[ReadingSessionId, HighlightId]],
    ) -> int: ...
