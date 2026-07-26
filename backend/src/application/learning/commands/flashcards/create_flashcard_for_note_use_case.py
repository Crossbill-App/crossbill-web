"""Use case for creating flashcards from notes."""

import structlog

from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects.ids import BookId, NoteId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.notes.exceptions import NoteNotFoundError

logger = structlog.get_logger(__name__)


class CreateFlashcardForNoteUseCase:
    """Use case for creating flashcards from notes."""

    def __init__(
        self,
        flashcard_repository: FlashcardRepositoryProtocol,
        note_repository: NoteRepositoryProtocol,
    ) -> None:
        """Initialize use case with repository protocols."""
        self.flashcard_repository = flashcard_repository
        self.note_repository = note_repository

    async def create_flashcard(
        self,
        note_id: int,
        user_id: int,
        question: str,
        answer: str,
        book_id: int | None = None,
    ) -> Flashcard:
        """
        Create a new flashcard linked to a note.

        Args:
            note_id: ID of the note
            user_id: ID of the user
            question: Question text for the flashcard
            answer: Answer text for the flashcard
            book_id: Book to file the flashcard under; must be linked to the
                note. Defaults to the note's first book.

        Returns:
            Created flashcard domain entity

        Raises:
            NoteNotFoundError: If note is not found
            ValidationError: If book_id is not linked to the note
        """
        note_id_vo = NoteId(note_id)
        user_id_vo = UserId(user_id)

        note = await self.note_repository.find_by_id(note_id_vo, user_id_vo)
        if not note:
            raise NoteNotFoundError(note_id)

        if book_id is not None and book_id not in note.book_ids:
            raise ValidationError(f"Book {book_id} is not linked to note {note_id}")
        resolved_book_id = book_id if book_id is not None else note.book_ids[0]

        flashcard = Flashcard.create(
            user_id=user_id_vo,
            book_id=BookId(resolved_book_id),
            question=question,
            answer=answer,
            note_id=note_id_vo,
        )
        flashcard = await self.flashcard_repository.save(flashcard)

        logger.info(
            "created_flashcard_for_note",
            flashcard_id=flashcard.id.value,
            note_id=note_id,
        )
        return flashcard
