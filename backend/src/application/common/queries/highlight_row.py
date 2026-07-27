"""The highlight row shared by the views that render a whole highlight.

The book-details page and the in-book highlight search show the same highlight
through the same ``Highlight`` response schema, so they read it through one
shape rather than two identical ones.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt

from src.application.common.queries.refs import FlashcardRef, TagRef


@dataclass(frozen=True)
class HighlightLabelView:
    """One highlight's effective label, resolved by the domain rather than by SQL."""

    highlight_style_id: int
    text: str | None
    ui_color: str | None


@dataclass(frozen=True)
class HighlightRow:
    """A highlight with everything a highlight list renders alongside it."""

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
