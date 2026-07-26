"""Create book use case."""

import logging

from src.application.library.dtos import CreateBookInput
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects import UserId
from src.domain.library.entities.book import Book

logger = logging.getLogger(__name__)


class CreateBookUseCase:
    """Use case for creating books."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository

    async def create_book(self, book_data: CreateBookInput, user_id: int) -> tuple[Book, bool]:
        """
        Get or create a book based on client_book_id.

        Args:
            book_data: Book creation data
            user_id: ID of the user

        Returns:
            tuple[Book, bool]: (book, created) where created is True if new book was created
        """
        # Convert primitives to value objects
        user_id_vo = UserId(user_id)

        # Primary lookup: client_book_id
        book = await self.book_repository.find_by_client_book_id(
            book_data.client_book_id, user_id_vo
        )
        if book:
            logger.debug(
                f"Found existing book by client_book_id: {book.title} (id={book.id.value})"
            )
            return book, False

        # Create new book using domain entity factory
        book = Book.create(
            user_id=user_id_vo,
            title=book_data.title,
            client_book_id=book_data.client_book_id,
            author=book_data.author,
            isbn=book_data.isbn,
            description=book_data.description,
            language=book_data.language,
            page_count=book_data.page_count,
        )

        # Save book
        book = await self.book_repository.save(book)

        return book, True
