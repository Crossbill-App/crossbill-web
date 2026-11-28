"""Read model for flashcards as review shows them.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass

from src.application.common.queries.refs import FlashcardRef
from src.domain.learning.value_objects.review_state import ReviewState


@dataclass(frozen=True)
class FlashcardInContextView(FlashcardRef):
    """A flashcard with its book, chapter and source, as review shows it.

    ``chapter_name`` is the flashcard's own chapter, else its highlight's.
    """

    book_title: str
    chapter_name: str | None
    highlight_text: str | None
    note_title: str | None
    review_state: ReviewState | None


@dataclass(frozen=True)
class FlashcardInContextPageView:
    """One page of a flashcard list, plus the length of the whole list."""

    flashcards: tuple[FlashcardInContextView, ...]
    total: int
