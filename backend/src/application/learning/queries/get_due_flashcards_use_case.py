"""Read use case for the queue of Due Cards."""

from datetime import datetime

from src.application.common.ownership import require_book
from src.application.learning.queries.due_flashcards import (
    DueFlashcardPageView,
    DueFlashcardQueryProtocol,
)
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects.ids import BookId, UserId


class GetDueFlashcardsUseCase:
    """Serve the cards a reader has to review, across the library or in one book."""

    def __init__(
        self,
        due_flashcard_query: DueFlashcardQueryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.due_flashcard_query = due_flashcard_query
        self.book_repository = book_repository

    async def get_due_flashcards(
        self, user_id: int, now: datetime, book_id: int | None, limit: int, offset: int
    ) -> DueFlashcardPageView:
        """Return a page of the queue as it stands at ``now``.

        Raises:
            BookNotFoundError: If a book is given and the user has no such book.
        """
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id) if book_id is not None else None
        if book_id_vo is not None:
            await require_book(self.book_repository, book_id_vo, user_id_vo)
        return await self.due_flashcard_query.list_due(user_id_vo, now, book_id_vo, limit, offset)
