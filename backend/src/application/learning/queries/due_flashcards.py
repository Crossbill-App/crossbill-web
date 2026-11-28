"""Read model for the queue of Due Flashcards.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.application.common.queries.refs import FlashcardRef
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.value_objects.flashcard_review import FlashcardRating
from src.domain.learning.value_objects.review_state import ReviewState


@dataclass(frozen=True)
class FlashcardInContextView(FlashcardRef):
    """A flashcard with its book, chapter and source, as review shows it.

    ``chapter_name`` is the flashcard's own chapter, else its highlight's.
    """

    book_title: str
    chapter_name: str | None
    highlight_text: str | None
    note_title: str | None
    review_state: ReviewState | None


@dataclass(frozen=True)
class FlashcardInContextPageView:
    """One page of the queue before previews, plus the length of the whole queue."""

    flashcards: tuple[FlashcardInContextView, ...]
    total: int


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
