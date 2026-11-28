"""Read use case for the list of Suspended flashcards."""

from src.application.common.ownership import require_book_if_given
from src.application.learning.queries.flashcards_in_context import FlashcardInContextPageView
from src.application.learning.queries.suspended_flashcards import (
    SuspendedFlashcardQueryProtocol,
)
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects.ids import UserId


class GetSuspendedFlashcardsUseCase:
    """Serve the flashcards a reader has suspended, across the library or in one book."""

    def __init__(
        self,
        suspended_flashcard_query: SuspendedFlashcardQueryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.suspended_flashcard_query = suspended_flashcard_query
        self.book_repository = book_repository

    async def get_suspended_flashcards(
        self, user_id: int, book_id: int | None, limit: int, offset: int
    ) -> FlashcardInContextPageView:
        """Return a page of the suspended flashcards.

        Raises:
            BookNotFoundError: If a book is given and the user has no such book.
        """
        user_id_vo = UserId(user_id)
        book_id_vo = await require_book_if_given(self.book_repository, book_id, user_id_vo)
        return await self.suspended_flashcard_query.list_suspended(
            user_id_vo, book_id_vo, limit, offset
        )
