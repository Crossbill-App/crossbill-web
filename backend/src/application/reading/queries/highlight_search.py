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

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class TagRef:
    """A tag on a matched highlight."""

    id: int
    name: str
    tag_group_id: int | None


@dataclass(frozen=True)
class FlashcardRef:
    """A flashcard made from a matched highlight."""

    id: int
    user_id: int
    book_id: int
    highlight_id: int | None
    chapter_id: int | None
    note_id: int | None
    question: str
    answer: str


@dataclass(frozen=True)
class HighlightLabelView:
    """A highlight's effective label, resolved by the domain rather than by SQL."""

    highlight_style_id: int
    text: str | None
    ui_color: str | None


@dataclass(frozen=True)
class SearchHighlightView:
    """A highlight that matched the search, with what the result list renders."""

    id: int
    book_id: int
    chapter_id: int | None
    chapter_name: str | None
    chapter_number: int | None
    text: str
    page: int | None
    datetime: str
    label: HighlightLabelView | None
    tags: tuple[TagRef, ...]
    flashcards: tuple[FlashcardRef, ...]
    created_at: dt
    updated_at: dt


@dataclass(frozen=True)
class SearchChapterView:
    """A chapter holding at least one matched highlight.

    ``updated_at`` mirrors the chapter's creation time, which is what this
    response has always reported; the search rows carry no parent chapter or
    start position, so the schema's fields for those stay null.
    """

    id: int
    name: str
    chapter_number: int | None
    highlights: tuple[SearchHighlightView, ...]
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
