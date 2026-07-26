"""AI-powered flashcard suggestions for notes."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status

from src.application.learning.queries.get_note_flashcard_suggestions_use_case import (
    GetNoteFlashcardSuggestionsUseCase,
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

router = APIRouter(prefix="/notes", tags=["flashcards"])


@router.get(
    "/{note_id}/flashcard_suggestions",
    response_model=CollectionResponse[FlashcardSuggestionItem],
    status_code=status.HTTP_200_OK,
)
@require_ai_enabled
async def get_note_flashcard_suggestions(
    note_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetNoteFlashcardSuggestionsUseCase = Depends(
        inject_use_case(container.learning.get_note_flashcard_suggestions_use_case)
    ),
) -> CollectionResponse[FlashcardSuggestionItem]:
    """
    Get AI-generated flashcard suggestions for a note.

    Suggestions are generated from the note's title, body and the text of
    its linked highlights.

    Args:
        note_id: ID of the note
        current_user: Authenticated user
        use_case: Use case injected via dependency container

    Returns:
        CollectionResponse with list of flashcard suggestions

    Raises:
        HTTPException 404: If note not found or not owned by user
    """
    suggestions_data = await use_case.get_suggestions(note_id, current_user.id.value)

    # Convert data classes to Pydantic schemas
    suggestions = [
        FlashcardSuggestionItem(question=s.question, answer=s.answer) for s in suggestions_data
    ]

    return CollectionResponse[FlashcardSuggestionItem](items=suggestions)
