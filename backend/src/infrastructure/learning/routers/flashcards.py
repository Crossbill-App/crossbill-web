"""API routes for flashcard management."""

from dataclasses import asdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.application.learning.commands.flashcards.delete_flashcard_use_case import (
    DeleteFlashcardUseCase,
)
from src.application.learning.commands.flashcards.record_flashcard_review_use_case import (
    RecordFlashcardReviewUseCase,
)
from src.application.learning.commands.flashcards.set_flashcard_status_use_case import (
    SetFlashcardStatusUseCase,
)
from src.application.learning.commands.flashcards.update_flashcard_use_case import (
    UpdateFlashcardUseCase,
)
from src.application.learning.queries.due_flashcards import DueFlashcardView
from src.application.learning.queries.get_due_flashcards_use_case import (
    GetDueFlashcardsUseCase,
)
from src.application.learning.queries.get_suspended_flashcards_use_case import (
    GetSuspendedFlashcardsUseCase,
)
from src.core import container
from src.domain.identity.entities.user import User
from src.domain.learning.value_objects.flashcard_review import FlashcardRating, FlashcardReview
from src.domain.learning.value_objects.flashcard_status import FlashcardStatus
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import PaginatedResponse, SuccessResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.learning.schemas import (
    DueFlashcard,
    Flashcard,
    FlashcardInContext,
    FlashcardReviewRequest,
    FlashcardStatusRequest,
    FlashcardUpdateRequest,
    FlashcardUpdateResponse,
)
from src.infrastructure.learning.schemas.flashcard_builders import (
    build_flashcard_schema,
)
from src.infrastructure.reading.routers.reader_clock import reader_now

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.get(
    "/due",
    response_model=PaginatedResponse[DueFlashcard],
    status_code=status.HTTP_200_OK,
)
async def get_due_flashcards(
    current_user: Annotated[User, Depends(get_current_user)],
    now: Annotated[datetime, Depends(reader_now)],
    book_id: int | None = Query(None, description="Only this book's cards"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum cards to return"),
    offset: int = Query(0, ge=0, description="Number of cards to skip"),
    use_case: GetDueFlashcardsUseCase = Depends(
        inject_use_case(container.learning.get_due_flashcards_use_case)
    ),
) -> PaginatedResponse[DueFlashcard]:
    """List the active flashcards to review now: due cards, then cards never reviewed.

    Due cards come lowest retrievability first; new cards follow one book at a
    time, in book order with those without a chapter last. Each flashcard carries
    `previews`: the exact due date each rating given now would set.
    """
    page = await use_case.get_due_flashcards(
        user_id=current_user.id.value, now=now, book_id=book_id, limit=limit, offset=offset
    )
    return PaginatedResponse[DueFlashcard](
        items=[_due_flashcard(card) for card in page.flashcards],
        total=page.total,
        offset=offset,
        limit=limit,
    )


def _due_flashcard(view: DueFlashcardView) -> DueFlashcard:
    return DueFlashcard.model_validate({**asdict(view.flashcard), "previews": view.previews})


@router.get(
    "/suspended",
    response_model=PaginatedResponse[FlashcardInContext],
    status_code=status.HTTP_200_OK,
)
async def get_suspended_flashcards(
    current_user: Annotated[User, Depends(get_current_user)],
    book_id: int | None = Query(None, description="Only this book's cards"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum cards to return"),
    offset: int = Query(0, ge=0, description="Number of cards to skip"),
    use_case: GetSuspendedFlashcardsUseCase = Depends(
        inject_use_case(container.learning.get_suspended_flashcards_use_case)
    ),
) -> PaginatedResponse[FlashcardInContext]:
    """List the suspended flashcards book by book, in chapter order with those without a chapter last."""
    page = await use_case.get_suspended_flashcards(
        user_id=current_user.id.value, book_id=book_id, limit=limit, offset=offset
    )
    return PaginatedResponse[FlashcardInContext](
        items=[FlashcardInContext.model_validate(card) for card in page.flashcards],
        total=page.total,
        offset=offset,
        limit=limit,
    )


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
    flashcard = build_flashcard_schema(flashcard_entity)
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


@router.post(
    "/{flashcard_id}/reviews",
    response_model=Flashcard,
    status_code=status.HTTP_200_OK,
)
async def record_flashcard_review(
    flashcard_id: int,
    request: FlashcardReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: RecordFlashcardReviewUseCase = Depends(
        inject_use_case(container.learning.record_flashcard_review_use_case)
    ),
) -> Flashcard:
    """Record a review of a flashcard and return the card as it is now scheduled.

    A review sent again with the same `reviewed_at` changes nothing. A suspended
    card takes no reviews (409).
    """
    flashcard = await use_case.record_review(
        flashcard_id=flashcard_id,
        user_id=current_user.id.value,
        review=FlashcardReview(
            rating=FlashcardRating(request.rating), reviewed_at=request.reviewed_at
        ),
    )
    return build_flashcard_schema(flashcard)


@router.put(
    "/{flashcard_id}/status",
    response_model=Flashcard,
    status_code=status.HTTP_200_OK,
)
async def set_flashcard_status(
    flashcard_id: int,
    request: FlashcardStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: SetFlashcardStatusUseCase = Depends(
        inject_use_case(container.learning.set_flashcard_status_use_case)
    ),
) -> Flashcard:
    """Suspend a flashcard, taking it out of review, or unsuspend it with its schedule intact."""
    flashcard = await use_case.set_status(
        flashcard_id=flashcard_id,
        user_id=current_user.id.value,
        status=FlashcardStatus(request.status),
    )
    return build_flashcard_schema(flashcard)
