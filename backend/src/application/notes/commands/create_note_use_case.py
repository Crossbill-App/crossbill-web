"""Use case for creating notes."""

import structlog

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.notes.commands.helpers import parse_note_kind, validate_link_targets
from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_enqueuer import EmbeddingEnqueuerProtocol
from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.notes.entities.note import Note

logger = structlog.get_logger(__name__)


class CreateNoteUseCase:
    """Use case for creating notes."""

    def __init__(
        self,
        note_repository: NoteRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        tag_repository: TagRepositoryProtocol,
        embedding_enqueuer: EmbeddingEnqueuerProtocol,
    ) -> None:
        self.note_repository = note_repository
        self.book_repository = book_repository
        self.chapter_repository = chapter_repository
        self.highlight_repository = highlight_repository
        self.tag_repository = tag_repository
        self._embedding_enqueuer = embedding_enqueuer

    async def create_note(
        self,
        user_id: int,
        title: str,
        body: str,
        kind: str | None,
        book_id: int,
        chapter_ids: list[int],
        highlight_ids: list[int],
        tag_ids: list[int],
    ) -> Note:
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        await validate_link_targets(
            user_id=user_id_vo,
            allowed_book_ids={book_id},
            chapter_ids=chapter_ids,
            highlight_ids=highlight_ids,
            tag_ids=tag_ids,
            chapter_repository=self.chapter_repository,
            highlight_repository=self.highlight_repository,
            tag_repository=self.tag_repository,
        )

        note = Note.create(
            user_id=user_id_vo,
            title=title,
            body=body,
            kind=parse_note_kind(kind),
            book_ids=[book_id],
            chapter_ids=chapter_ids,
            highlight_ids=highlight_ids,
            tag_ids=tag_ids,
        )
        note = await self.note_repository.save(note)

        await self._embedding_enqueuer.enqueue_for(ContentType.NOTE, note.id.value, user_id)

        logger.info("created_note", note_id=note.id.value, book_id=book_id)
        return note
