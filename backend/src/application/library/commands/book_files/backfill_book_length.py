"""Fill in the length of a book stored before its EPUB was measured."""

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.domain.common.value_objects.position import Position
from src.domain.common.value_objects.position_index import PositionIndex
from src.domain.library.entities.book import Book


async def backfill_book_length(
    book: Book,
    index: PositionIndex,
    book_repository: BookRepositoryProtocol,
    chapter_repository: ChapterRepositoryProtocol,
) -> None:
    """Store the book's end position, character total and chapter offsets where missing.

    An upload measures all three at once, so a book with a total already has its
    chapters' offsets, and only a book without one costs the chapter lookup.
    """
    if index.total_elements == 0:
        return
    if book.end_position is not None and book.total_characters is not None:
        return

    if book.end_position is None:
        book.update_end_position(Position(index=index.total_elements, char_index=0))
    if book.total_characters is None:
        book.update_total_characters(index.total_characters)
        chapters = await chapter_repository.find_all_by_book(book.id, book.user_id)
        offsets = {
            chapter.id: offset
            for chapter in chapters
            if chapter.start_xpoint is not None
            and chapter.start_offset is None
            and (offset := index.character_offset(chapter.start_xpoint)) is not None
        }
        await chapter_repository.set_start_offsets(offsets)
    await book_repository.save(book)
