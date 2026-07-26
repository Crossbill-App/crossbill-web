"""Use case for recording that a user opened a book."""

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects import BookId, UserId


class MarkBookViewedUseCase:
    """Stamp a book's ``last_viewed`` timestamp."""

    def __init__(self, book_repository: BookRepositoryProtocol) -> None:
        self.book_repository = book_repository

    async def mark_viewed(self, book_id: int, user_id: int) -> None:
        """Mark the user's book as viewed now.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        book = await require_book(self.book_repository, BookId(book_id), UserId(user_id))
        book.mark_as_viewed()
        await self.book_repository.save(book)
