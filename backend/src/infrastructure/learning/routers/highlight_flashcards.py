"""Flashcard endpoints scoped to highlights."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.learning.use_cases.flashcards.create_flashcard_for_highlight_use_case import (
    CreateFlashcardForHighlightUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import (
    Flashcard,
    FlashcardCreateRequest,
    FlashcardCreateResponse,
)

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
    # Manually construct Pydantic schema from domain entity
    flashcard = Flashcard(
        id=flashcard_entity.id.value,
        user_id=flashcard_entity.user_id.value,
        book_id=flashcard_entity.book_id.value,
        highlight_id=flashcard_entity.highlight_id.value if flashcard_entity.highlight_id else None,
        question=flashcard_entity.question,
        answer=flashcard_entity.answer,
    )
    return FlashcardCreateResponse(
        success=True,
        message="Flashcard created successfully",
        flashcard=flashcard,
    )
