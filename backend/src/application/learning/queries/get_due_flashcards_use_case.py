"""Read use case for the queue of Due Flashcards."""

from datetime import datetime

from src.application.common.ownership import require_book_if_given
from src.application.learning.protocols.review_scheduler import ReviewScheduler
from src.application.learning.queries.due_flashcards import (
    DueFlashcardPageView,
    DueFlashcardQueryProtocol,
    DueFlashcardView,
)
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects.ids import UserId


class GetDueFlashcardsUseCase:
    """Serve the cards a reader has to review, across the library or in one book."""

    def __init__(
        self,
        due_flashcard_query: DueFlashcardQueryProtocol,
        book_repository: BookRepositoryProtocol,
        review_scheduler: ReviewScheduler,
    ) -> None:
        self.due_flashcard_query = due_flashcard_query
        self.book_repository = book_repository
        self.review_scheduler = review_scheduler

    async def get_due_flashcards(
        self, user_id: int, now: datetime, book_id: int | None, limit: int, offset: int
    ) -> DueFlashcardPageView:
        """Return a page of the queue as it stands at ``now``, with each flashcard's rating previews.

        Raises:
            BookNotFoundError: If a book is given and the user has no such book.
        """
        user_id_vo = UserId(user_id)
        book_id_vo = await require_book_if_given(self.book_repository, book_id, user_id_vo)
        page = await self.due_flashcard_query.list_due(user_id_vo, now, book_id_vo, limit, offset)
        return DueFlashcardPageView(
            flashcards=tuple(
                DueFlashcardView(
                    flashcard=card, previews=self.review_scheduler.preview(card.review_state, now)
                )
                for card in page.flashcards
            ),
            total=page.total,
        )
