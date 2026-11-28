"""Flashcard endpoints scoped to highlights."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.learning.commands.flashcards.create_flashcard_for_highlight_use_case import (
    CreateFlashcardForHighlightUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import (
    FlashcardCreateRequest,
    FlashcardCreateResponse,
)
from src.infrastructure.learning.schemas.flashcard_builders import build_flashcard_schema

router = APIRouter(prefix="/highlights", tags=["flashcards"])


@router.post(
    "/{highlight_id}/flashcards",
    response_model=FlashcardCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flashcard_for_highlight(
    highlight_id: int,
    request: FlashcardCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CreateFlashcardForHighlightUseCase = Depends(
        inject_use_case(container.learning.create_flashcard_for_highlight_use_case)
    ),
) -> FlashcardCreateResponse:
    """
    Create a flashcard for a highlight.

    Creates a flashcard that is associated with a specific highlight.
    The flashcard will also be linked to the highlight's book.

    Args:
        highlight_id: ID of the highlight
        request: Request containing question and answer
        use_case: Use case injected via dependency container

    Returns:
        Created flashcard

    Raises:
        HTTPException: If highlight not found or creation fails
    """
    flashcard_entity = await use_case.create_flashcard(
        highlight_id=highlight_id,
        user_id=current_user.id.value,
        question=request.question,
        answer=request.answer,
    )
    flashcard = build_flashcard_schema(flashcard_entity)
    return FlashcardCreateResponse(
        success=True,
        message="Flashcard created successfully",
        flashcard=flashcard,
    )
