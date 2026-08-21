"""Read model for a book's reading-session list.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.application.common.queries.highlight_row import HighlightLabelView
from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class SessionHighlightView:
    """A highlight recorded during a session.

    Deliberately thinner than the book-details highlight: this list has never
    carried a session highlight's chapter, tags or flashcards.
    """

    id: int
    book_id: int
    chapter_id: int | None
    text: str
    page: int | None
    datetime: str
    label: HighlightLabelView | None
    removed_from_devices: bool
    created_at: dt
    updated_at: dt


@dataclass(frozen=True)
class ReadingSessionView:
    """One reading session as the list renders it.

    ``content`` is the session's text read back out of the EPUB. It stays
    ``None`` when the book has no EPUB, when the session recorded no position,
    or when extraction fails -- a session that cannot be re-read is still a
    session worth listing.
    """

    id: int
    book_id: int
    device_id: str | None
    content_hash: str
    start_time: dt
    end_time: dt
    start_page: int | None
    end_page: int | None
    content: str | None
    ai_summary: str | None
    created_at: dt
    highlights: tuple[SessionHighlightView, ...]


@dataclass(frozen=True)
class ReadingSessionPageView:
    """One page of a book's reading sessions, plus the unpaginated total."""

    sessions: tuple[ReadingSessionView, ...]
    total: int


class ReadingSessionQueryProtocol(Protocol):
    """Port for reading a book's session list."""

    async def list_for_book(
        self, book_id: BookId, user_id: UserId, limit: int, offset: int
    ) -> ReadingSessionPageView | None:
        """Return a page of sessions newest first, or ``None`` if the user has no such book."""
        ...
