"""Read model for the queue of Due Cards.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.application.common.queries.refs import FlashcardRef
from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class DueFlashcardPageView:
    """One page of the queue, plus the length of the whole queue."""

    flashcards: tuple[FlashcardRef, ...]
    total: int


class DueFlashcardQueryProtocol(Protocol):
    """Port for reading the user's Due Cards."""

    async def list_due(
        self, user_id: UserId, now: datetime, book_id: BookId | None, limit: int, offset: int
    ) -> DueFlashcardPageView:
        """Return a page of the active cards due by ``now`` or never reviewed.

        Due reviews come first, lowest retrievability first; then new cards one
        book at a time, in book order with chapterless ones last.
        """
        ...
