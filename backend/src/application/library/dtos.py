"""Application-layer DTOs for library module."""

from dataclasses import dataclass, field

from src.application.reading.services.highlight_grouping_service import ChapterWithHighlights
from src.domain.common.value_objects.position import Position
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.library.entities.book import Book
from src.domain.reading.entities.bookmark import Bookmark
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.domain.tagging.entities.tag import Tag
from src.domain.tagging.entities.tag_group import TagGroup


@dataclass
class BookDetailsAggregation:
    """Aggregated book data for detail view."""

    book: Book
    tags: list[Tag]
    tag_groups: list[TagGroup]
    bookmarks: list[Bookmark]
    chapters_with_highlights: list[ChapterWithHighlights]
    book_flashcards: list[Flashcard] = field(default_factory=list)
    reading_position: Position | None = None
    labels: dict[int, ResolvedLabel] = field(default_factory=dict)


@dataclass
class CreateBookInput:
    """Input data for creating a book."""

    title: str
    client_book_id: str
    author: str | None = None
    isbn: str | None = None
    description: str | None = None
    language: str | None = None
    page_count: int | None = None
