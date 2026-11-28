"""Response-schema builder for a flashcard aggregate."""

from src.domain.learning.entities.flashcard import Flashcard
from src.infrastructure.learning.schemas.flashcard_schemas import Flashcard as FlashcardSchema


def build_flashcard_schema(flashcard: Flashcard) -> FlashcardSchema:
    """Render a flashcard aggregate."""
    return FlashcardSchema(
        id=flashcard.id.value,
        user_id=flashcard.user_id.value,
        book_id=flashcard.book_id.value,
        highlight_id=flashcard.highlight_id.value if flashcard.highlight_id else None,
        chapter_id=flashcard.chapter_id.value if flashcard.chapter_id else None,
        note_id=flashcard.note_id.value if flashcard.note_id else None,
        question=flashcard.question,
        answer=flashcard.answer,
        status=flashcard.status.value,
        origin=flashcard.origin.value,
        due=flashcard.review_state.due if flashcard.review_state else None,
        last_review=flashcard.review_state.last_review if flashcard.review_state else None,
    )
