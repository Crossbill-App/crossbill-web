"""AI-powered flashcard suggestions for chapters."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status

from src.application.learning.queries.get_chapter_flashcard_suggestions_use_case import (
    GetChapterFlashcardSuggestionsUseCase,
)
from src.core import container
from src.domain.identity.entities.user import User
from src.infrastructure.common.dependencies import require_ai_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.learning.schemas import (
    FlashcardSuggestionItem,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chapters", tags=["flashcards"])


@router.get(
    "/{chapter_id}/flashcard_suggestions",
    response_model=CollectionResponse[FlashcardSuggestionItem],
    status_code=status.HTTP_200_OK,
)
@require_ai_enabled
async def get_chapter_flashcard_suggestions(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetChapterFlashcardSuggestionsUseCase = Depends(
        inject_use_case(container.learning.get_chapter_flashcard_suggestions_use_case)
    ),
) -> CollectionResponse[FlashcardSuggestionItem]:
    """
    Get AI-generated flashcard suggestions from a chapter digest.

    Requires the chapter to have a generated pre-reading summary.
    """
    suggestions_data = await use_case.get_suggestions(chapter_id, current_user.id.value)

    suggestions = [
        FlashcardSuggestionItem(question=s.question, answer=s.answer) for s in suggestions_data
    ]

    return CollectionResponse[FlashcardSuggestionItem](items=suggestions)
