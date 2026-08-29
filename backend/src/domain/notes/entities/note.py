"""Note entity for user-authored book notes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from src.domain.common.aggregate_root import AggregateRoot
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import NoteId, UserId


class NoteKind(StrEnum):
    """Optional classification of a note."""

    CHARACTER = "character"
    TERM = "term"
    CONCEPT = "concept"
    GIST = "gist"
    REFLECTION = "reflection"
    OTHER = "other"


UNCOUNTED_NOTE_KINDS: frozenset[NoteKind] = frozenset({NoteKind.GIST})
"""Kinds left out when notes are counted, matching the Notes tab's default filter.

A note with no kind counts: untyped notes read as "other".
"""


@dataclass
class Note(AggregateRoot[NoteId]):
    """
    User-authored note about a term, character, or concept.

    Business Rules:
    - Title cannot be empty
    - A note must be linked to at least one book
    - Body may be empty (a bare title is a valid note)

    Cross-aggregate validation (linked chapters/highlights/tags must belong
    to a linked book) is performed in the application layer, which can load
    the referenced aggregates.
    """

    id: NoteId
    user_id: UserId
    title: str
    body: str = ""
    kind: NoteKind | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Link-id collections (association rows persisted by infrastructure)
    book_ids: list[int] = field(default_factory=list)
    chapter_ids: list[int] = field(default_factory=list)
    highlight_ids: list[int] = field(default_factory=list)
    tag_ids: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate invariants."""
        self._validate_title(self.title)
        self._validate_books(self.book_ids)

    def update_content(self, title: str, body: str, kind: NoteKind | None) -> None:
        """Update title, body and kind."""
        self._validate_title(title)
        self.title = title.strip()
        self.body = body
        self.kind = kind

    def replace_links(
        self,
        book_ids: list[int],
        chapter_ids: list[int],
        highlight_ids: list[int],
        tag_ids: list[int],
    ) -> None:
        """Replace all link sets."""
        self._validate_books(book_ids)
        self.book_ids = list(book_ids)
        self.chapter_ids = list(chapter_ids)
        self.highlight_ids = list(highlight_ids)
        self.tag_ids = list(tag_ids)

    @staticmethod
    def _validate_title(title: str) -> None:
        if not title or not title.strip():
            raise ValidationError("Note title cannot be empty")

    @staticmethod
    def _validate_books(book_ids: list[int]) -> None:
        if not book_ids:
            raise ValidationError("Note must be linked to at least one book")

    @classmethod
    def create(
        cls,
        user_id: UserId,
        title: str,
        book_ids: list[int],
        body: str = "",
        kind: NoteKind | None = None,
        chapter_ids: list[int] | None = None,
        highlight_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
    ) -> Note:
        """Create a new note (ID will be 0 until persisted)."""
        return cls(
            id=NoteId.generate(),
            user_id=user_id,
            title=title.strip() if title else title,
            body=body,
            kind=kind,
            book_ids=list(book_ids),
            chapter_ids=list(chapter_ids or []),
            highlight_ids=list(highlight_ids or []),
            tag_ids=list(tag_ids or []),
        )

    @classmethod
    def create_with_id(
        cls,
        id: NoteId,
        user_id: UserId,
        title: str,
        body: str,
        kind: NoteKind | None,
        created_at: datetime,
        updated_at: datetime,
        book_ids: list[int],
        chapter_ids: list[int],
        highlight_ids: list[int],
        tag_ids: list[int],
    ) -> Note:
        """Reconstitute a note from persistence."""
        return cls(
            id=id,
            user_id=user_id,
            title=title,
            body=body,
            kind=kind,
            created_at=created_at,
            updated_at=updated_at,
            book_ids=book_ids,
            chapter_ids=chapter_ids,
            highlight_ids=highlight_ids,
            tag_ids=tag_ids,
        )
