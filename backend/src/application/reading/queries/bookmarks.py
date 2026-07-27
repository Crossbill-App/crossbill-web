"""Read model for a book's bookmark list.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from typing import Protocol

from src.application.common.queries.refs import BookmarkView
from src.domain.common.value_objects.ids import BookId, UserId


class BookmarkQueryProtocol(Protocol):
    """Port for reading a book's bookmarks."""

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[BookmarkView, ...] | None:
        """Return the book's bookmarks newest first, or ``None`` if the user has no such book."""
        ...
