"""Use case for creating standalone flashcards for books."""

import structlog

from src.application.common.ownership import require_belongs_to_book, require_book
from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.domain.common.value_objects.ids import BookId, ChapterId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.reading.exceptions import ChapterNotFoundError

logger = structlog.get_logger(__name__)


class CreateFlashcardForBookUseCase:
    """Use case for creating standalone flashcards for books."""

    def __init__(
        self,
        flashcard_repository: FlashcardRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
    ) -> None:
        """Initialize use case with repository protocols."""
        self.flashcard_repository = flashcard_repository
        self.book_repository = book_repository
        self.chapter_repository = chapter_repository

    async def create_flashcard(
        self,
        book_id: int,
        user_id: int,
        question: str,
        answer: str,
        chapter_id: int | None = None,
    ) -> Flashcard:
        """
        Create a new standalone flashcard for a book (without a highlight).

        Args:
            book_id: ID of the book
            user_id: ID of the user
            question: Question text for the flashcard
            answer: Answer text for the flashcard
            chapter_id: Optional ID of the chapter

        Returns:
            Created flashcard domain entity

        Raises:
            BookNotFoundError: If book is not found
            ChapterNotFoundError: If chapter is not found or belongs to another book
        """
        # Convert to value objects
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        # Validate book exists and belongs to user
        await require_book(self.book_repository, book_id_vo, user_id_vo)

        # Validate chapter if provided
        chapter_id_vo: ChapterId | None = None
        if chapter_id is not None:
            chapter_id_vo = ChapterId(chapter_id)
            chapter = await self.chapter_repository.find_by_id(chapter_id_vo, user_id_vo)
            if not chapter:
                raise ChapterNotFoundError(chapter_id)
            # A chapter from another book is indistinguishable from a missing one.
            require_belongs_to_book(chapter, book_id_vo, lambda: ChapterNotFoundError(chapter_id))

        # Create flashcard using domain factory (no highlight)
        flashcard = Flashcard.create(
            user_id=user_id_vo,
            book_id=book_id_vo,
            question=question,
            answer=answer,
            highlight_id=None,
            chapter_id=chapter_id_vo,
        )

        # Persist (commit handled by DI infrastructure)
        flashcard = await self.flashcard_repository.save(flashcard)

        logger.info(
            "created_flashcard_for_book",
            flashcard_id=flashcard.id.value,
            book_id=book_id,
        )
        return flashcard
