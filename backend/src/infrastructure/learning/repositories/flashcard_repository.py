"""Repository for Flashcard domain entities."""

from sqlalchemy import Insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.entity import EntityId
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.exceptions import FlashcardNotFoundError
from src.domain.learning.value_objects.flashcard_review import FlashcardReview
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.common.sql import is_postgres
from src.infrastructure.learning.mappers.flashcard_mapper import FlashcardMapper
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.learning.orm.flashcard_review_model import (
    FlashcardReview as FlashcardReviewORM,
)


class FlashcardRepository(BaseRepository[Flashcard, FlashcardORM]):
    """Repository for Flashcard domain entities.

    ``delete`` is inherited from :class:`BaseRepository` (ownership scoped by
    ``user_id``); ``find_by_id`` and ``save`` also carry the card's reviews.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.mapper = FlashcardMapper()
        super().__init__(db, FlashcardORM, self.mapper)

    async def find_by_id(self, entity_id: EntityId, user_id: UserId) -> Flashcard | None:
        """Load an owned flashcard with every review it has."""
        stmt = select(FlashcardORM).where(
            FlashcardORM.id == entity_id.value, FlashcardORM.user_id == user_id.value
        )
        orm_model = (await self.db.execute(stmt)).scalar_one_or_none()
        if orm_model is None:
            return None
        return self.mapper.to_domain(orm_model, await self._reviews_of(orm_model.id))

    async def save(self, flashcard: Flashcard, /) -> Flashcard:
        """Insert or update a flashcard together with its new reviews.

        A new review the store already holds discards the whole save, as the card's
        stored state already counts it; the stored card is returned instead.
        """
        if flashcard.id.value == 0:
            orm_model = self.mapper.to_orm(flashcard)
            self.db.add(orm_model)
        else:
            stored = await self.db.get(FlashcardORM, flashcard.id.value)
            if stored is None:
                raise FlashcardNotFoundError(flashcard.id.value)
            orm_model = self.mapper.to_orm(flashcard, stored)
        await self.db.flush()

        if not await self._insert_new_reviews(orm_model.id, flashcard.new_reviews):
            await self.db.rollback()
            reloaded = await self.find_by_id(flashcard.id, flashcard.user_id)
            if reloaded is None:
                raise FlashcardNotFoundError(flashcard.id.value)
            return reloaded

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

    async def _reviews_of(self, flashcard_id: int) -> list[FlashcardReview]:
        stmt = select(FlashcardReviewORM).where(FlashcardReviewORM.flashcard_id == flashcard_id)
        rows = (await self.db.execute(stmt)).scalars().all()
        return [self.mapper.review_to_domain(row) for row in rows]

    async def _insert_new_reviews(
        self, flashcard_id: int, reviews: tuple[FlashcardReview, ...]
    ) -> bool:
        """Insert the reviews, skipping any the store holds; whether every one went in."""
        if not reviews:
            return True
        stmt = (
            self._insert_or_ignore()
            .values([self.mapper.review_values(flashcard_id, review) for review in reviews])
            .returning(FlashcardReviewORM.id)
        )
        inserted = (await self.db.execute(stmt)).all()
        return len(inserted) == len(reviews)

    def _insert_or_ignore(self) -> Insert:
        unique_key = ["flashcard_id", "reviewed_at"]
        if is_postgres(self.db):
            return pg_insert(FlashcardReviewORM).on_conflict_do_nothing(index_elements=unique_key)
        return sqlite_insert(FlashcardReviewORM).on_conflict_do_nothing(index_elements=unique_key)
