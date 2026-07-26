"""Flashcard endpoints scoped to notes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.learning.commands.flashcards.create_flashcard_for_note_use_case import (
    CreateFlashcardForNoteUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import (
    Flashcard,
    FlashcardCreateResponse,
    NoteFlashcardCreateRequest,
)

router = APIRouter(prefix="/notes", tags=["flashcards"])


@router.post(
    "/{note_id}/flashcards",
    response_model=FlashcardCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flashcard_for_note(
    note_id: int,
    request: NoteFlashcardCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CreateFlashcardForNoteUseCase = Depends(
        inject_use_case(container.learning.create_flashcard_for_note_use_case)
    ),
) -> FlashcardCreateResponse:
    """
    Create a flashcard linked to a note.

    The flashcard is filed under the requested book (which must be linked to
    the note), or the note's first book when no book is given.

    Args:
        note_id: ID of the note
        request: Request containing question, answer and optional book_id
        use_case: Use case injected via dependency container

    Returns:
        Created flashcard

    Raises:
        HTTPException: If note not found or book is not linked to the note
    """
    flashcard_entity = await use_case.create_flashcard(
        note_id=note_id,
        user_id=current_user.id.value,
        question=request.question,
        answer=request.answer,
        book_id=request.book_id,
    )
    # Manually construct Pydantic schema from domain entity
    flashcard = Flashcard(
        id=flashcard_entity.id.value,
        user_id=flashcard_entity.user_id.value,
        book_id=flashcard_entity.book_id.value,
        highlight_id=flashcard_entity.highlight_id.value if flashcard_entity.highlight_id else None,
        chapter_id=flashcard_entity.chapter_id.value if flashcard_entity.chapter_id else None,
        note_id=flashcard_entity.note_id.value if flashcard_entity.note_id else None,
        question=flashcard_entity.question,
        answer=flashcard_entity.answer,
    )
    return FlashcardCreateResponse(
        success=True,
        message="Flashcard created successfully",
        flashcard=flashcard,
    )
