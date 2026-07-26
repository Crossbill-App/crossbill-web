"""Read model for the book-details view.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.library.entities.book import ReadingStage


@dataclass(frozen=True)
class TagRef:
    """A tag as shown inside a book."""

    id: int
    name: str
    tag_group_id: int | None


@dataclass(frozen=True)
class TagGroupRef:
    """A tag group as shown inside a book."""

    id: int
    name: str


@dataclass(frozen=True)
class BookmarkView:
    """A bookmark pinned to one of the book's highlights."""

    id: int
    book_id: int
    highlight_id: int
    created_at: dt


@dataclass(frozen=True)
class FlashcardRef:
    """A flashcard as shown in the book-details view."""

    id: int
    user_id: int
    book_id: int
    highlight_id: int | None
    chapter_id: int | None
    question: str
    answer: str


@dataclass(frozen=True)
class HighlightLabelView:
    """The label resolved for a highlight's style."""

    highlight_style_id: int
    text: str | None
    ui_color: str | None


@dataclass(frozen=True)
class HighlightView:
    """A highlight with everything the book-details view renders alongside it."""

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
class ChapterWithHighlightsView:
    """A chapter of the book together with its highlights (possibly none)."""

    id: int
    name: str
    chapter_number: int | None
    parent_id: int | None
    start_position: Position | None
    highlights: tuple[HighlightView, ...]
    created_at: dt
    updated_at: dt


@dataclass(frozen=True)
class BookDetailsView:
    """Everything the book-details page renders, in one purpose-built shape."""

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
    reading_stage: ReadingStage | None
    tags: tuple[TagRef, ...]
    tag_groups: tuple[TagGroupRef, ...]
    bookmarks: tuple[BookmarkView, ...]
    book_flashcards: tuple[FlashcardRef, ...]
    chapters: tuple[ChapterWithHighlightsView, ...]
    reading_position: Position | None
    end_position: Position | None
    created_at: dt
    updated_at: dt
    last_viewed: dt | None


class BookDetailsQueryProtocol(Protocol):
    """Port for reading the book-details view."""

    async def get_book_details(self, book_id: BookId, user_id: UserId) -> BookDetailsView | None:
        """Return the view for a user's book, or ``None`` when they have no such book."""
        ...
