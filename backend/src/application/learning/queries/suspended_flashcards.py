"""Read model for the list of Suspended flashcards."""

from typing import Protocol

from src.application.learning.queries.flashcards_in_context import FlashcardInContextPageView
from src.domain.common.value_objects.ids import BookId, UserId


class SuspendedFlashcardQueryProtocol(Protocol):
    """Port for reading the user's Suspended flashcards."""

    async def list_suspended(
        self, user_id: UserId, book_id: BookId | None, limit: int, offset: int
    ) -> FlashcardInContextPageView:
        """Return a page of the suspended flashcards, book by book in book order."""
        ...
