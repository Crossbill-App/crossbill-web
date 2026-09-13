from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from src.application.web_reader.anchors import Locator
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

    async def bulk_update_positions(
        self,
        position_updates: list[tuple[ReadingSessionId, Position, Position]],
    ) -> int: ...

    async def bulk_update_locators(
        self,
        locators: Mapping[ReadingSessionId, tuple[Locator | None, Locator | None]],
        source_hash: str,
    ) -> None:
        """Write both endpoints' derived Locators and their source digest onto stored sessions.

        The pair is (start, end); one digest covers the batch, since a sync
        derives every session of one book against one EPUB.
        """
        ...

    async def link_highlights_to_sessions(
        self,
        session_highlight_pairs: list[tuple[ReadingSessionId, HighlightId]],
    ) -> int: ...
