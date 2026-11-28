"""Query adapter for the list of Suspended flashcards."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.learning.queries.review_flashcards import ReviewFlashcardPageView
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.learning.queries.review_flashcard_rows import (
    review_flashcard_page,
)


class SuspendedFlashcardQuery:
    """Serves the Suspended flashcards from one ordered select and a count."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_suspended(
        self, user_id: UserId, book_id: BookId | None, limit: int, offset: int
    ) -> ReviewFlashcardPageView:
        """Return a page of the suspended flashcards, book by book in book order."""
        suspended = FlashcardORM.status == FlashcardStatus.SUSPENDED.value
        return await review_flashcard_page(self.db, user_id, book_id, [suspended], limit, offset)
