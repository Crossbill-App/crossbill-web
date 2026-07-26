"""Read use case for the single-note view."""

from src.application.notes.queries.note_with_links import (
    NoteQueryProtocol,
    NoteWithLinksView,
)
from src.domain.common.value_objects import NoteId, UserId
from src.domain.notes.exceptions import NoteNotFoundError


class GetNoteUseCase:
    """Serve one note with its linked entities and its flashcards."""

    def __init__(self, note_query: NoteQueryProtocol) -> None:
        self.note_query = note_query

    async def get_note(self, note_id: int, user_id: int) -> NoteWithLinksView:
        """Return the note view.

        Raises:
            NoteNotFoundError: If the user has no such note.
        """
        view = await self.note_query.get_note(NoteId(note_id), UserId(user_id))
        if view is None:
            raise NoteNotFoundError(note_id)
        return view
