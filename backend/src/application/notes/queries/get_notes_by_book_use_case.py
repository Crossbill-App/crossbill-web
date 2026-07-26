"""Read use case for the per-book note list."""

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.notes.queries.note_with_links import (
    NoteQueryProtocol,
    NoteWithLinksView,
)
from src.application.notes.use_cases.helpers import parse_note_kind
from src.domain.common.value_objects import BookId, ChapterId, HighlightId, TagId, UserId


class GetNotesByBookUseCase:
    """Serve a book's notes with their linked entities."""

    def __init__(
        self,
        note_query: NoteQueryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.note_query = note_query
        self.book_repository = book_repository

    async def get_notes(
        self,
        book_id: int,
        user_id: int,
        kind: str | None = None,
        chapter_id: int | None = None,
        highlight_id: int | None = None,
        tag_id: int | None = None,
    ) -> tuple[NoteWithLinksView, ...]:
        """Return the book's notes.

        Raises:
            BookNotFoundError: If the user has no such book.
            ValidationError: If ``kind`` is not a known note kind.
        """
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        return await self.note_query.list_for_book(
            book_id_vo,
            user_id_vo,
            kind=parse_note_kind(kind),
            chapter_id=ChapterId(chapter_id) if chapter_id is not None else None,
            highlight_id=HighlightId(highlight_id) if highlight_id is not None else None,
            tag_id=TagId(tag_id) if tag_id is not None else None,
        )
