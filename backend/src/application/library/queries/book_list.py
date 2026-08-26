"""Read model for the two book-list views.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.

The library list and the recently-viewed list render the same response schema,
so they share one DTO and one port with a method each.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.common.value_objects.ids import UserId
from src.domain.common.value_objects.position import Position


@dataclass(frozen=True)
class BookWithCountsView:
    """A book as the library lists render it, with its highlight and card counts."""

    id: int
    client_book_id: str | None
    title: str
    author: str | None
    isbn: str | None
    cover_file: str | None
    cover_blurhash: str | None
    description: str | None
    language: str | None
    page_count: int | None
    highlight_count: int
    flashcard_count: int
    end_position: Position | None
    created_at: datetime
    updated_at: datetime
    last_viewed: datetime | None
    last_synced: datetime | None


@dataclass(frozen=True)
class BookListPageView:
    """One page of the library list, with the unpaginated total beside it."""

    books: tuple[BookWithCountsView, ...]
    total: int


class BookListQueryProtocol(Protocol):
    """Port for reading a user's books as a list."""

    async def list_books(
        self,
        user_id: UserId,
        offset: int,
        limit: int,
        include_only_with_flashcards: bool,
        search_text: str | None,
    ) -> BookListPageView:
        """Return a page of the user's books ordered by title, plus the total."""
        ...

    async def list_recently_viewed(
        self, user_id: UserId, limit: int
    ) -> tuple[BookWithCountsView, ...]:
        """Return the books the user has opened, most recently viewed first."""
        ...
