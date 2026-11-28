"""Mapper for Flashcard ORM ↔ Domain conversion."""

from collections.abc import Sequence

from src.domain.common.time import as_aware
from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    FlashcardId,
    HighlightId,
    NoteId,
    UserId,
)
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.value_objects.flashcard_origin import FlashcardOrigin
from src.domain.learning.value_objects.flashcard_review import FlashcardRating, FlashcardReview
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus
from src.domain.learning.value_objects.review_state import ReviewPhase, ReviewState
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.learning.orm.flashcard_review_model import (
    FlashcardReview as FlashcardReviewORM,
)


class FlashcardMapper:
    """Mapper for Flashcard ORM ↔ Domain conversion."""

    def to_domain(
        self, orm_model: FlashcardORM, reviews: Sequence[FlashcardReview] = ()
    ) -> Flashcard:
        """Convert ORM model to domain entity, with whichever of its reviews were loaded."""
        return Flashcard.create_with_id(
            id=FlashcardId(orm_model.id),
            user_id=UserId(orm_model.user_id),
            book_id=BookId(orm_model.book_id),
            question=orm_model.question,
            answer=orm_model.answer,
            highlight_id=HighlightId(orm_model.highlight_id) if orm_model.highlight_id else None,
            chapter_id=ChapterId(orm_model.chapter_id) if orm_model.chapter_id else None,
            note_id=NoteId(orm_model.note_id) if orm_model.note_id else None,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
            origin=FlashcardOrigin(orm_model.origin),
            status=FlashcardStatus(orm_model.status),
            review_state=_review_state(orm_model),
            reviews=tuple(reviews),
        )

    def to_orm(
        self, domain_entity: Flashcard, orm_model: FlashcardORM | None = None
    ) -> FlashcardORM:
        """Convert domain entity to ORM model."""
        if orm_model is None:
            orm_model = FlashcardORM(
                id=orm_id(domain_entity.id),
            )
        orm_model.user_id = domain_entity.user_id.value
        orm_model.book_id = domain_entity.book_id.value
        orm_model.question = domain_entity.question
        orm_model.answer = domain_entity.answer
        orm_model.highlight_id = (
            domain_entity.highlight_id.value if domain_entity.highlight_id else None
        )
        orm_model.chapter_id = domain_entity.chapter_id.value if domain_entity.chapter_id else None
        orm_model.note_id = domain_entity.note_id.value if domain_entity.note_id else None
        orm_model.origin = domain_entity.origin.value
        orm_model.status = domain_entity.status.value
        _write_review_state(orm_model, domain_entity.review_state)
        return orm_model

    def review_to_domain(self, orm_model: FlashcardReviewORM) -> FlashcardReview:
        """Convert a review row to its value object."""
        return FlashcardReview(
            rating=FlashcardRating(orm_model.rating),
            reviewed_at=as_aware(orm_model.reviewed_at),
        )

    def review_to_orm(self, flashcard_id: int, review: FlashcardReview) -> FlashcardReviewORM:
        """Convert a review of the given flashcard to a new row."""
        return FlashcardReviewORM(
            flashcard_id=flashcard_id,
            rating=review.rating.value,
            reviewed_at=review.reviewed_at,
        )


def _review_state(orm_model: FlashcardORM) -> ReviewState | None:
    if (
        orm_model.fsrs_state is None
        or orm_model.stability is None
        or orm_model.difficulty is None
        or orm_model.due is None
        or orm_model.last_review is None
    ):
        return None
    return ReviewState(
        phase=ReviewPhase(orm_model.fsrs_state),
        step=orm_model.step,
        stability=orm_model.stability,
        difficulty=orm_model.difficulty,
        due=as_aware(orm_model.due),
        last_review=as_aware(orm_model.last_review),
    )


def _write_review_state(orm_model: FlashcardORM, state: ReviewState | None) -> None:
    if state is None:
        orm_model.fsrs_state = orm_model.step = orm_model.stability = None
        orm_model.difficulty = orm_model.due = orm_model.last_review = None
        return
    orm_model.fsrs_state = state.phase.value
    orm_model.step = state.step
    orm_model.stability = state.stability
    orm_model.difficulty = state.difficulty
    orm_model.due = state.due
    orm_model.last_review = state.last_review
