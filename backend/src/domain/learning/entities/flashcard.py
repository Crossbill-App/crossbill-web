"""
Flashcard entity for spaced repetition learning.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.common.entity import Entity
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    FlashcardId,
    HighlightId,
    NoteId,
    UserId,
)
from src.domain.learning.exceptions import FlashcardSuspendedError
from src.domain.learning.value_objects.flashcard_origin import FlashcardOrigin
from src.domain.learning.value_objects.flashcard_review import FlashcardReview, ReviewArrival
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus
from src.domain.learning.value_objects.review_state import ReviewState


@dataclass
class Flashcard(Entity[FlashcardId]):
    """
    Flashcard for creating study cards from highlights.

    Business Rules:
    - Question and answer cannot be empty
    - Flashcard can optionally be linked to a highlight, chapter, or note
    - Flashcard must be associated with a book
    - A suspended flashcard takes no reviews
    - Its review state is derived from its Flashcard Reviews, at most one per instant
    """

    id: FlashcardId
    user_id: UserId
    book_id: BookId
    question: str
    answer: str
    highlight_id: HighlightId | None = None
    chapter_id: ChapterId | None = None
    note_id: NoteId | None = None
    origin: FlashcardOrigin = FlashcardOrigin.MANUAL
    status: FlashcardStatus = FlashcardStatus.ACTIVE
    review_state: ReviewState | None = None

    _reviews: list[FlashcardReview] = field(default_factory=list, repr=False)
    _pending_review: FlashcardReview | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.question or not self.question.strip():
            raise DomainError("Question cannot be empty")
        if not self.answer or not self.answer.strip():
            raise DomainError("Answer cannot be empty")

    def update_question(self, question: str) -> None:
        """
        Update the question.

        Args:
            question: New question text

        Raises:
            DomainError: If question is empty
        """
        if not question or not question.strip():
            raise DomainError("Question cannot be empty")
        self.question = question.strip()

    def update_answer(self, answer: str) -> None:
        """
        Update the answer.

        Args:
            answer: New answer text

        Raises:
            DomainError: If answer is empty
        """
        if not answer or not answer.strip():
            raise DomainError("Answer cannot be empty")
        self.answer = answer.strip()

    @property
    def reviews(self) -> tuple[FlashcardReview, ...]:
        """Every review the card has: the stored ones in time order, then any just recorded."""
        return tuple(self._reviews)

    @property
    def pending_review(self) -> FlashcardReview | None:
        """The review recorded since the card was loaded, for the repository to insert."""
        return self._pending_review

    def record_review(self, review: FlashcardReview) -> ReviewArrival:
        """Add a review to the card's log, saying how its review state must follow.

        Raises:
            FlashcardSuspendedError: If the card is suspended.
        """
        if self.status is FlashcardStatus.SUSPENDED:
            raise FlashcardSuspendedError(self.id.value)
        if self._has_review_at(review.reviewed_at):
            return ReviewArrival.DUPLICATE
        arrival = (
            ReviewArrival.IN_ORDER if self._follows_last_review(review) else ReviewArrival.LATE
        )
        self._reviews.append(review)
        self._pending_review = review
        return arrival

    def apply_review_state(self, review_state: ReviewState) -> None:
        """Take the review state the card's reviews were scheduled to."""
        self.review_state = review_state

    def set_status(self, status: FlashcardStatus) -> None:
        """Suspend or unsuspend the card, keeping its review state as it is."""
        self.status = status

    def _has_review_at(self, moment: datetime) -> bool:
        return any(review.reviewed_at == moment for review in self._reviews)

    def _follows_last_review(self, review: FlashcardReview) -> bool:
        return self.review_state is None or review.reviewed_at > self.review_state.last_review

    @classmethod
    def create(
        cls,
        user_id: UserId,
        book_id: BookId,
        question: str,
        answer: str,
        highlight_id: HighlightId | None = None,
        chapter_id: ChapterId | None = None,
        note_id: NoteId | None = None,
    ) -> "Flashcard":
        """Create a new flashcard (ID will be 0 until persisted)."""
        return cls(
            id=FlashcardId.generate(),
            user_id=user_id,
            book_id=book_id,
            question=question.strip(),
            answer=answer.strip(),
            highlight_id=highlight_id,
            chapter_id=chapter_id,
            note_id=note_id,
        )

    @classmethod
    def create_with_id(
        cls,
        id: FlashcardId,
        user_id: UserId,
        book_id: BookId,
        question: str,
        answer: str,
        created_at: datetime,
        updated_at: datetime,
        highlight_id: HighlightId | None = None,
        chapter_id: ChapterId | None = None,
        note_id: NoteId | None = None,
        origin: FlashcardOrigin = FlashcardOrigin.MANUAL,
        status: FlashcardStatus = FlashcardStatus.ACTIVE,
        review_state: ReviewState | None = None,
        reviews: tuple[FlashcardReview, ...] = (),
    ) -> "Flashcard":
        """Reconstitute a flashcard from persistence."""
        return cls(
            id=id,
            user_id=user_id,
            book_id=book_id,
            question=question,
            answer=answer,
            highlight_id=highlight_id,
            chapter_id=chapter_id,
            note_id=note_id,
            origin=origin,
            status=status,
            review_state=review_state,
            _reviews=list(reviews),
        )
