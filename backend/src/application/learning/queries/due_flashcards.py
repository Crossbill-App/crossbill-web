"""Read model for the queue of Due Flashcards.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.application.learning.queries.flashcards_in_context import (
    FlashcardInContextPageView,
    FlashcardInContextView,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.value_objects.flashcard_review import FlashcardRating


@dataclass(frozen=True)
class DueFlashcardView:
    """A Due Flashcard and the due date each rating given now would set."""

    flashcard: FlashcardInContextView
    previews: Mapping[FlashcardRating, datetime]


@dataclass(frozen=True)
class DueFlashcardPageView:
    """One page of the queue, plus the length of the whole queue."""

    flashcards: tuple[DueFlashcardView, ...]
    total: int


class DueFlashcardQueryProtocol(Protocol):
    """Port for reading the user's Due Flashcards."""

    async def list_due(
        self, user_id: UserId, now: datetime, book_id: BookId | None, limit: int, offset: int
    ) -> FlashcardInContextPageView:
        """Return a page of the active cards due by ``now`` or never reviewed.

        Due reviews come first, lowest retrievability first; then new cards one
        book at a time, in book order with chapterless ones last.
        """
        ...
