"""Use case for creating or updating a book's reflection."""

import structlog

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.application.reflection.protocols.book_reflection_repository import (
    BookReflectionRepositoryProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.notes.exceptions import NoteNotFoundError
from src.domain.reflection.entities.book_reflection import BookReflection

logger = structlog.get_logger(__name__)


class UpsertBookReflectionUseCase:
    """Create or update the single reflection for a book (full replace)."""

    def __init__(
        self,
        book_reflection_repository: BookReflectionRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
        note_repository: NoteRepositoryProtocol,
    ) -> None:
        self.book_reflection_repository = book_reflection_repository
        self.book_repository = book_repository
        self.note_repository = note_repository

    async def upsert_reflection(
        self,
        book_id: int,
        user_id: int,
        what_is_it_about_note_id: int | None,
        what_does_it_say_note_id: int | None,
        do_i_agree_note_id: int | None,
        so_what_note_id: int | None,
        note_ids: list[int],
    ) -> BookReflection:
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        answer_note_ids = [
            note_id
            for note_id in (
                what_is_it_about_note_id,
                what_does_it_say_note_id,
                do_i_agree_note_id,
                so_what_note_id,
            )
            if note_id is not None
        ]
        await self._validate_notes_belong_to_book(
            book_id_vo, user_id_vo, [*answer_note_ids, *note_ids]
        )

        reflection = await self.book_reflection_repository.find_by_book_id(book_id_vo, user_id_vo)
        if reflection is None:
            reflection = BookReflection.create(user_id=user_id_vo, book_id=book_id_vo)

        reflection.update_answer_notes(
            what_is_it_about_note_id=what_is_it_about_note_id,
            what_does_it_say_note_id=what_does_it_say_note_id,
            do_i_agree_note_id=do_i_agree_note_id,
            so_what_note_id=so_what_note_id,
        )
        reflection.replace_note_links(note_ids)
        reflection = await self.book_reflection_repository.save(reflection)

        logger.info("upserted_book_reflection", book_id=book_id, note_count=len(note_ids))
        return reflection

    async def _validate_notes_belong_to_book(
        self,
        book_id: BookId,
        user_id: UserId,
        note_ids: list[int],
    ) -> None:
        """Reject any requested note that is not one of this book's own notes."""
        if not note_ids:
            return
        book_notes = await self.note_repository.find_by_book(book_id, user_id)
        valid_ids = {note.id.value for note in book_notes}
        for note_id in note_ids:
            if note_id not in valid_ids:
                raise NoteNotFoundError(note_id)
