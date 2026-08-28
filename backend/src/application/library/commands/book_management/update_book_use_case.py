"""Use case for editing a book's own fields."""

import structlog

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects import BookId, UserId
from src.domain.library.entities.book import Book

logger = structlog.get_logger(__name__)


class UpdateBookUseCase:
    """Apply user edits to a book's own fields."""

    def __init__(self, book_repository: BookRepositoryProtocol) -> None:
        self.book_repository = book_repository

    async def update_description(
        self,
        book_id: int,
        user_id: int,
        description: str | None,
    ) -> Book:
        book = await require_book(self.book_repository, BookId(book_id), UserId(user_id))
        book.set_description(description)
        book = await self.book_repository.save(book)
        logger.info("updated_book_description", book_id=book_id, cleared=book.description is None)
        return book
