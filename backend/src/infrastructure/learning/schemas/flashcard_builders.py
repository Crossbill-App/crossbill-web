"""Response-schema builders for a flashcard, from the aggregate or from a view row."""

from src.application.common.queries.refs import FlashcardRef
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
    )


def build_flashcard_ref_schema(card: FlashcardRef) -> FlashcardSchema:
    """Render a flashcard embedded in a read model."""
    return FlashcardSchema(
        id=card.id,
        user_id=card.user_id,
        book_id=card.book_id,
        highlight_id=card.highlight_id,
        chapter_id=card.chapter_id,
        note_id=card.note_id,
        question=card.question,
        answer=card.answer,
    )
