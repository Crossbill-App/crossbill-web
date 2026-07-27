"""View DTOs that several read models embed.

Each is a flat projection of one row, carrying only the fields a view renders.
They live here rather than in a module's ``queries`` package because more than
one view needs the identical shape.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt


@dataclass(frozen=True)
class TagRef:
    """A tag as a view renders it."""

    id: int
    name: str
    tag_group_id: int | None


@dataclass(frozen=True)
class FlashcardRef:
    """A flashcard as a view renders it."""

    id: int
    user_id: int
    book_id: int
    highlight_id: int | None
    chapter_id: int | None
    note_id: int | None
    question: str
    answer: str


@dataclass(frozen=True)
class BookmarkView:
    """A bookmark pinned to one of a book's highlights."""

    id: int
    book_id: int
    highlight_id: int
    created_at: dt
