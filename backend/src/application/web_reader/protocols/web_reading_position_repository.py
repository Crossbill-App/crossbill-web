"""Port for the store behind a book's last web-reader position."""

from typing import Protocol

from src.domain.common.value_objects import BookId, UserId
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition


class WebReadingPositionRepositoryProtocol(Protocol):
    """Persistence for :class:`WebReadingPosition`, one row per reader and book."""

    async def find_for_book(self, book_id: BookId, user_id: UserId) -> WebReadingPosition | None:
        """Return where this reader last was in this book, or ``None`` if never here."""
        ...

    async def save(self, position: WebReadingPosition) -> WebReadingPosition:
        """Insert the position or update the one already stored for its book."""
        ...
