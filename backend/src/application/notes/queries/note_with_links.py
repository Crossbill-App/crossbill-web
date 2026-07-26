"""Read model for the note views.

The detail endpoint and the per-book list endpoint render the same response
schema, so they share one view DTO and one port with a method each.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.domain.common.value_objects.ids import (
    BookId,
    ChapterId,
    HighlightId,
    NoteId,
    TagId,
    UserId,
)
from src.domain.notes.entities.note import NoteKind


@dataclass(frozen=True)
class LinkedChapterView:
    """A chapter linked to a note, as the note views show it."""

    id: int
    name: str


@dataclass(frozen=True)
class LinkedHighlightView:
    """A highlight linked to a note, as the note views show it."""

    id: int
    text: str


@dataclass(frozen=True)
class LinkedTagView:
    """A tag linked to a note, as the note views show it."""

    id: int
    name: str


@dataclass(frozen=True)
class NoteFlashcardView:
    """A flashcard generated from a note."""

    id: int
    user_id: int
    book_id: int
    highlight_id: int | None
    chapter_id: int | None
    note_id: int | None
    question: str
    answer: str


@dataclass(frozen=True)
class NoteWithLinksView:
    """A note together with the entities it links to.

    The ``*_ids`` tuples are the note's raw link sets, while ``chapters``,
    ``highlights`` and ``tags`` carry only the links the viewer may actually
    see: a link to a soft-deleted highlight or to another user's row keeps its
    id but resolves to nothing.

    Both query methods fill every field. The list view used to leave
    ``flashcards`` empty, which made a list row an incomplete stand-in for a
    detail row -- and the frontend seeds its detail cache from list rows.
    """

    id: int
    user_id: int
    title: str
    body: str
    kind: NoteKind | None
    book_ids: tuple[int, ...]
    chapter_ids: tuple[int, ...]
    highlight_ids: tuple[int, ...]
    tag_ids: tuple[int, ...]
    chapters: tuple[LinkedChapterView, ...]
    highlights: tuple[LinkedHighlightView, ...]
    tags: tuple[LinkedTagView, ...]
    flashcards: tuple[NoteFlashcardView, ...]
    created_at: dt
    updated_at: dt


class NoteQueryProtocol(Protocol):
    """Port for reading the note views."""

    async def get_note(self, note_id: NoteId, user_id: UserId) -> NoteWithLinksView | None:
        """Return one of the user's notes, or ``None`` when they have no such note."""
        ...

    async def list_for_book(
        self,
        book_id: BookId,
        user_id: UserId,
        kind: NoteKind | None = None,
        chapter_id: ChapterId | None = None,
        highlight_id: HighlightId | None = None,
        tag_id: TagId | None = None,
    ) -> tuple[NoteWithLinksView, ...]:
        """Return the user's notes for a book, ordered by title."""
        ...
