"""AI-powered features for highlights."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status

from src.application.learning.queries.get_flashcard_suggestions_use_case import (
    GetFlashcardSuggestionsUseCase,
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

router = APIRouter(prefix="/highlights", tags=["flashcards"])


@router.get(
    "/{highlight_id}/flashcard_suggestions",
    response_model=CollectionResponse[FlashcardSuggestionItem],
    status_code=status.HTTP_200_OK,
)
@require_ai_enabled
async def get_highlight_flashcard_suggestions(
    highlight_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetFlashcardSuggestionsUseCase = Depends(
        inject_use_case(container.learning.get_flashcard_suggestions_use_case)
    ),
) -> CollectionResponse[FlashcardSuggestionItem]:
    """
    Get AI-generated flashcard suggestions for a highlight.

    Args:
        highlight_id: ID of the highlight
        current_user: Authenticated user
        use_case: FlashcardAIUseCase injected via dependency container

    Returns:
        CollectionResponse with list of flashcard suggestions

    Raises:
        HTTPException 404: If highlight not found or not owned by user
    """
    suggestions_data = await use_case.get_suggestions(highlight_id, current_user.id.value)

    # Convert data classes to Pydantic schemas
    suggestions = [
        FlashcardSuggestionItem(question=s.question, answer=s.answer) for s in suggestions_data
    ]

    return CollectionResponse[FlashcardSuggestionItem](items=suggestions)
