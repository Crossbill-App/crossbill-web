"""Use case for retrieving notes for a book with linked entities."""

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.application.notes.use_cases.dtos import NoteWithLinkedEntities
from src.application.notes.use_cases.helpers import hydrate_note_links, parse_note_kind
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects import BookId, ChapterId, HighlightId, TagId, UserId


class GetNotesByBookUseCase:
    """Use case for retrieving notes for a book with linked entities."""

    def __init__(
        self,
        note_repository: NoteRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        tag_repository: TagRepositoryProtocol,
    ) -> None:
        self.note_repository = note_repository
        self.book_repository = book_repository
        self.chapter_repository = chapter_repository
        self.highlight_repository = highlight_repository
        self.tag_repository = tag_repository

    async def get_notes(
        self,
        book_id: int,
        user_id: int,
        kind: str | None = None,
        chapter_id: int | None = None,
        highlight_id: int | None = None,
        tag_id: int | None = None,
    ) -> list[NoteWithLinkedEntities]:
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        notes = await self.note_repository.find_by_book(
            book_id_vo,
            user_id_vo,
            kind=parse_note_kind(kind),
            chapter_id=ChapterId(chapter_id) if chapter_id is not None else None,
            highlight_id=HighlightId(highlight_id) if highlight_id is not None else None,
            tag_id=(TagId(tag_id) if tag_id is not None else None),
        )
        return await hydrate_note_links(
            notes,
            user_id_vo,
            chapter_repository=self.chapter_repository,
            highlight_repository=self.highlight_repository,
            tag_repository=self.tag_repository,
        )
