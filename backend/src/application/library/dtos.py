"""Application-layer DTOs for library module."""

from dataclasses import dataclass, field
from typing import Any

from src.application.reading.services.highlight_grouping_service import ChapterWithHighlights
from src.domain.common.value_objects.position import Position
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.library.entities.book import Book
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel


@dataclass
class BookDetailsAggregation:
    """Aggregated book data for detail view."""

    book: Book
    tags: list[Any]  # Legacy ORM models (temporary)
    tag_groups: list[Any]  # Legacy ORM models (temporary)
    bookmarks: list[Any]  # Legacy ORM models (temporary)
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
