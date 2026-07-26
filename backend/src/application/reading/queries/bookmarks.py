"""Read model for a book's bookmark list.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class BookmarkView:
    """A bookmark pinned to one of the book's highlights."""

    id: int
    book_id: int
    highlight_id: int
    created_at: dt


class BookmarkQueryProtocol(Protocol):
    """Port for reading a book's bookmarks."""

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[BookmarkView, ...] | None:
        """Return the book's bookmarks newest first, or ``None`` if the user has no such book."""
        ...
