"""Use case for recording a Flashcard Review."""

import structlog

from src.application.common.ownership import require_flashcard
from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.application.learning.protocols.review_scheduler import ReviewScheduler
from src.domain.common.value_objects.ids import FlashcardId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.value_objects.flashcard_review import FlashcardReview, ReviewArrival

logger = structlog.get_logger(__name__)


class RecordFlashcardReviewUseCase:
    """Log a review of a flashcard and reschedule the card from it."""

    def __init__(
        self,
        flashcard_repository: FlashcardRepositoryProtocol,
        review_scheduler: ReviewScheduler,
    ) -> None:
        self.flashcard_repository = flashcard_repository
        self.review_scheduler = review_scheduler

    async def record_review(
        self, flashcard_id: int, user_id: int, review: FlashcardReview
    ) -> Flashcard:
        """Record the review, returning the card as rescheduled; a re-sent one changes nothing.

        Raises:
            FlashcardNotFoundError: If the user has no such flashcard.
            FlashcardSuspendedError: If the flashcard is suspended.
        """
        flashcard = await require_flashcard(
            self.flashcard_repository, FlashcardId(flashcard_id), UserId(user_id), for_update=True
        )

        arrival = flashcard.record_review(review)
        if arrival is ReviewArrival.DUPLICATE:
            return flashcard

        if arrival is ReviewArrival.IN_ORDER:
            state = self.review_scheduler.review(flashcard.review_state, review)
        else:
            state = self.review_scheduler.replay(flashcard.reviews)
        flashcard.apply_review_state(state)

        flashcard = await self.flashcard_repository.save(flashcard)
        logger.info("recorded_flashcard_review", flashcard_id=flashcard_id, arrival=arrival.value)
        return flashcard
