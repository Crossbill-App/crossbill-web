"""Protocol for Note repository."""

from typing import Protocol

from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    HighlightId,
    NoteId,
    TagId,
    UserId,
)
from src.domain.notes.entities.note import Note, NoteKind


class NoteRepositoryProtocol(Protocol):
    """Protocol for Note repository operations."""

    async def find_by_id(self, note_id: NoteId, /, user_id: UserId) -> Note | None:
        """Find a note by id, scoped to the user."""
        ...

    async def find_by_book(
        self,
        book_id: BookId,
        user_id: UserId,
        kind: NoteKind | None = None,
        chapter_id: ChapterId | None = None,
        highlight_id: HighlightId | None = None,
        tag_id: TagId | None = None,
    ) -> list[Note]:
        """Find notes linked to a book, with optional filters."""
        ...

    async def save(self, note: Note, /) -> Note:
        """Create or update a note, replacing association rows."""
        ...

    async def delete(self, note_id: NoteId, /, user_id: UserId) -> bool:
        """Delete a note. Returns False if not found."""
        ...
