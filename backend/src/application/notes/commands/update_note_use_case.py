"""Use case for updating notes."""

import structlog

from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.notes.commands.helpers import parse_note_kind, validate_link_targets
from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_enqueuer import EmbeddingEnqueuerProtocol
from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects import NoteId, UserId
from src.domain.notes.entities.note import Note
from src.domain.notes.exceptions import NoteNotFoundError

logger = structlog.get_logger(__name__)


class UpdateNoteUseCase:
    """Use case for updating notes (full replace of content and links)."""

    def __init__(
        self,
        note_repository: NoteRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        tag_repository: TagRepositoryProtocol,
        embedding_enqueuer: EmbeddingEnqueuerProtocol,
    ) -> None:
        self.note_repository = note_repository
        self.chapter_repository = chapter_repository
        self.highlight_repository = highlight_repository
        self.tag_repository = tag_repository
        self._embedding_enqueuer = embedding_enqueuer

    async def update_note(
        self,
        note_id: int,
        user_id: int,
        title: str,
        body: str,
        kind: str | None,
        chapter_ids: list[int],
        highlight_ids: list[int],
        tag_ids: list[int],
    ) -> Note:
        user_id_vo = UserId(user_id)
        note = await self.note_repository.find_by_id(NoteId(note_id), user_id_vo)
        if not note:
            raise NoteNotFoundError(note_id)

        await validate_link_targets(
            user_id=user_id_vo,
            allowed_book_ids=set(note.book_ids),
            chapter_ids=chapter_ids,
            highlight_ids=highlight_ids,
            tag_ids=tag_ids,
            chapter_repository=self.chapter_repository,
            highlight_repository=self.highlight_repository,
            tag_repository=self.tag_repository,
        )

        note.update_content(title=title, body=body, kind=parse_note_kind(kind))
        note.replace_links(
            book_ids=note.book_ids,  # book links unchanged in v1
            chapter_ids=chapter_ids,
            highlight_ids=highlight_ids,
            tag_ids=tag_ids,
        )
        note = await self.note_repository.save(note)

        await self._embedding_enqueuer.enqueue_for(ContentType.NOTE, note.id.value, user_id)

        logger.info("updated_note", note_id=note_id)
        return note
