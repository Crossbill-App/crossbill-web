"""API routes for flashcard management."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.application.learning.commands.flashcards.delete_flashcard_use_case import (
    DeleteFlashcardUseCase,
)
from src.application.learning.commands.flashcards.update_flashcard_use_case import (
    UpdateFlashcardUseCase,
)
from src.core import container
from src.domain.identity.entities.user import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import SuccessResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.learning.schemas import (
    Flashcard,
    FlashcardUpdateRequest,
    FlashcardUpdateResponse,
)

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.put(
    "/{flashcard_id}",
    response_model=FlashcardUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_flashcard(
    flashcard_id: int,
    request: FlashcardUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: UpdateFlashcardUseCase = Depends(
        inject_use_case(container.learning.update_flashcard_use_case)
    ),
) -> FlashcardUpdateResponse:
    """
    Update a flashcard's question and/or answer.

    Args:
        flashcard_id: ID of the flashcard to update
        request: Request containing updated question and/or answer
        use_case: FlashcardUseCase injected via dependency container

    Returns:
        Updated flashcard

    Raises:
        HTTPException: If flashcard not found or update fails
    """
    flashcard_entity = await use_case.update_flashcard(
        flashcard_id=flashcard_id,
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
    return FlashcardUpdateResponse(
        success=True,
        message="Flashcard updated successfully",
        flashcard=flashcard,
    )


@router.delete(
    "/{flashcard_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_flashcard(
    flashcard_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: DeleteFlashcardUseCase = Depends(
        inject_use_case(container.learning.delete_flashcard_use_case)
    ),
) -> SuccessResponse:
    """
    Delete a flashcard.

    Args:
        flashcard_id: ID of the flashcard to delete
        use_case: FlashcardUseCase injected via dependency container

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: If flashcard not found or deletion fails
    """
    await use_case.delete_flashcard(flashcard_id=flashcard_id, user_id=current_user.id.value)
    return SuccessResponse(
        success=True,
        message="Flashcard deleted successfully",
    )
