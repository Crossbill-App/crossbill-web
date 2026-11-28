"""Repository for Flashcard domain entities."""

from typing import Any

from sqlalchemy import Select, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.entity import EntityId
from src.domain.common.value_objects.ids import BookId, FlashcardId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.exceptions import FlashcardNotFoundError
from src.domain.learning.value_objects.flashcard_review import FlashcardReview
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.learning.mappers.flashcard_mapper import FlashcardMapper
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.learning.orm.flashcard_review_model import (
    FlashcardReview as FlashcardReviewORM,
)


class FlashcardRepository(BaseRepository[Flashcard, FlashcardORM]):
    """Repository for Flashcard domain entities.

    ``delete`` is inherited from :class:`BaseRepository` (ownership scoped by
    ``user_id``); the finders and ``save`` also carry the card's reviews.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.mapper = FlashcardMapper()
        super().__init__(db, FlashcardORM, self.mapper)

    async def find_by_id(self, entity_id: EntityId, user_id: UserId) -> Flashcard | None:
        """Load an owned flashcard with every review it has."""
        return await self._find(self._owned(entity_id, user_id))

    async def find_by_id_for_update(
        self, flashcard_id: FlashcardId, user_id: UserId
    ) -> Flashcard | None:
        """Load an owned flashcard with its reviews, locking its row until the next save."""
        return await self._find(self._owned(flashcard_id, user_id).with_for_update())

    async def save(self, flashcard: Flashcard, /) -> Flashcard:
        """Insert or update a flashcard together with its pending review."""
        if flashcard.id.value == 0:
            orm_model = self.mapper.to_orm(flashcard)
            self.db.add(orm_model)
        else:
            stored = await self.db.get(FlashcardORM, flashcard.id.value)
            if stored is None:
                raise FlashcardNotFoundError(flashcard.id.value)
            orm_model = self.mapper.to_orm(flashcard, stored)
        await self.db.flush()

        if flashcard.pending_review is not None:
            await self.db.execute(
                insert(FlashcardReviewORM).values(
                    self.mapper.review_values(orm_model.id, flashcard.pending_review)
                )
            )

        await self.db.commit()
        await self.db.refresh(orm_model)
        return self.mapper.to_domain(orm_model, flashcard.reviews)

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

    def _owned(self, flashcard_id: EntityId, user_id: UserId) -> Select[Any]:
        return select(FlashcardORM).where(
            FlashcardORM.id == flashcard_id.value, FlashcardORM.user_id == user_id.value
        )

    async def _find(self, stmt: Select[Any]) -> Flashcard | None:
        orm_model = (await self.db.execute(stmt)).scalar_one_or_none()
        if orm_model is None:
            return None
        return self.mapper.to_domain(orm_model, await self._reviews_of(orm_model.id))

    async def _reviews_of(self, flashcard_id: int) -> list[FlashcardReview]:
        stmt = (
            select(FlashcardReviewORM)
            .where(FlashcardReviewORM.flashcard_id == flashcard_id)
            .order_by(FlashcardReviewORM.reviewed_at)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [self.mapper.review_to_domain(row) for row in rows]
