"""Read model for a book's flashcard list.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class TagRef:
    """A tag on a flashcard's highlight, as the list shows it."""

    id: int
    name: str
    tag_group_id: int | None


@dataclass(frozen=True)
class HighlightLabelView:
    """A highlight's effective label, resolved by the domain rather than by SQL."""

    highlight_style_id: int | None
    text: str | None
    ui_color: str | None


@dataclass(frozen=True)
class FlashcardHighlightView:
    """The highlight a flashcard was made from, embedded in the flashcard row."""

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
    created_at: dt
    updated_at: dt


@dataclass(frozen=True)
class FlashcardWithHighlightView:
    """A flashcard of a book together with the highlight it came from.

    ``highlight_id`` is the flashcard's own column while ``highlight`` holds the
    row only when the viewer may actually see it: a card pointing at a
    soft-deleted or another user's highlight keeps its id and renders as
    nothing. That is the API's behaviour, so the DTO carries both.

    There is deliberately no ``note_id``: the endpoint has never returned one,
    even though the response schema declares the field.
    """

    id: int
    user_id: int
    book_id: int
    highlight_id: int | None
    chapter_id: int | None
    question: str
    answer: str
    highlight: FlashcardHighlightView | None


class BookFlashcardQueryProtocol(Protocol):
    """Port for reading a book's flashcard list."""

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[FlashcardWithHighlightView, ...]:
        """Return the user's flashcards for a book, newest first."""
        ...
