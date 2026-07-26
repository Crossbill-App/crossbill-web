"""Use case for deleting notes."""

import structlog

from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.domain.common.value_objects import NoteId, UserId
from src.domain.notes.exceptions import NoteNotFoundError

logger = structlog.get_logger(__name__)


class DeleteNoteUseCase:
    """Use case for deleting notes."""

    def __init__(self, note_repository: NoteRepositoryProtocol) -> None:
        self.note_repository = note_repository

    async def delete_note(self, note_id: int, user_id: int) -> None:
        deleted = await self.note_repository.delete(NoteId(note_id), UserId(user_id))
        if not deleted:
            raise NoteNotFoundError(note_id)
        logger.info("deleted_note", note_id=note_id)
