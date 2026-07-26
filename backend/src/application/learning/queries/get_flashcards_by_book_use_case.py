"""Read use case for a book's flashcard list."""

from src.application.common.ownership import require_book
from src.application.learning.queries.book_flashcards import (
    BookFlashcardQueryProtocol,
    FlashcardWithHighlightView,
)
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects.ids import BookId, UserId


class GetFlashcardsByBookUseCase:
    """Serve a book's flashcards with the highlights they came from."""

    def __init__(
        self,
        book_flashcard_query: BookFlashcardQueryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.book_flashcard_query = book_flashcard_query
        self.book_repository = book_repository

    async def get_flashcards(
        self, book_id: int, user_id: int
    ) -> tuple[FlashcardWithHighlightView, ...]:
        """Return the book's flashcards.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        return await self.book_flashcard_query.list_for_book(book_id_vo, user_id_vo)
