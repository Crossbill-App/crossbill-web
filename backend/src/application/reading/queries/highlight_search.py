"""Read model for the in-book highlight search.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.

This view is what ADR-0001 opens with. It used to arrive as
``list[tuple[Highlight, Book, Chapter | None, list[Tag], list[Flashcard]]]``
from ``HighlightRepositoryProtocol.search`` -- a view row wearing domain
clothes, whose ``Book`` element every caller discarded.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.application.common.queries.highlight_row import HighlightRow
from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class SearchChapterView:
    """A chapter holding at least one matched highlight.

    The search rows carry no parent chapter or start position, so the schema's
    fields for those stay null.
    """

    id: int
    name: str
    chapter_number: int | None
    highlights: tuple[HighlightRow, ...]
    created_at: dt
    updated_at: dt


@dataclass(frozen=True)
class BookHighlightSearchView:
    """The matched highlights of a book, grouped by chapter.

    ``total`` counts the highlights actually rendered: a match whose chapter is
    unknown belongs to no group, and has never been listed or counted.
    """

    chapters: tuple[SearchChapterView, ...]
    total: int


class HighlightSearchQueryProtocol(Protocol):
    """Port for searching a book's highlights."""

    async def search_in_book(
        self, book_id: BookId, user_id: UserId, search_text: str, limit: int = 100
    ) -> BookHighlightSearchView | None:
        """Return the matches grouped by chapter, or ``None`` if the user has no such book."""
        ...
