"""Repository for Flashcard domain entities."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.learning.mappers.flashcard_mapper import FlashcardMapper
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM


class FlashcardRepository(BaseRepository[Flashcard, FlashcardORM]):
    """Repository for Flashcard domain entities.

    ``find_by_id``, ``save`` and ``delete`` are inherited from
    :class:`BaseRepository` (ownership scoped by ``user_id``).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.mapper = FlashcardMapper()
        super().__init__(db, FlashcardORM, self.mapper)

    async def find_by_book(self, book_id: BookId, user_id: UserId) -> list[Flashcard]:
        """
        Get all flashcards for a book.

        Args:
            book_id: The book ID
            user_id: The user ID for ownership verification

        Returns:
            List of flashcard entities ordered by created_at DESC
        """
        stmt = (
            select(FlashcardORM)
            .where(
                FlashcardORM.book_id == book_id.value,
                FlashcardORM.user_id == user_id.value,
            )
            .order_by(FlashcardORM.created_at.desc())
        )
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()
        return [self.mapper.to_domain(orm) for orm in orm_models]

    async def count_by_book(self, book_id: BookId, user_id: UserId) -> int:
        """
        Count flashcards for a book.

        Args:
            book_id: The book ID
            user_id: The user ID for ownership verification

        Returns:
            Count of flashcards
        """
        stmt = select(func.count(FlashcardORM.id)).where(
            FlashcardORM.book_id == book_id.value,
            FlashcardORM.user_id == user_id.value,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
