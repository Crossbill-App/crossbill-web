from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.learning.commands.flashcards.create_flashcard_for_book_use_case import (
    CreateFlashcardForBookUseCase,
)
from src.application.learning.queries.book_flashcards import (
    FlashcardHighlightView,
    FlashcardWithHighlightView,
)
from src.application.learning.queries.get_flashcards_by_book_use_case import (
    GetFlashcardsByBookUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import (
    Flashcard,
    FlashcardCreateRequest,
    FlashcardCreateResponse,
    FlashcardWithHighlight,
)
from src.infrastructure.reading.schemas import (
    HighlightLabel,
    HighlightResponseBase,
)
from src.infrastructure.tagging.schemas import TagInBook

router = APIRouter(prefix="/books", tags=["flashcards"])


@router.post(
    "/{book_id}/flashcards",
    response_model=FlashcardCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flashcard_for_book(
    book_id: int,
    request: FlashcardCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CreateFlashcardForBookUseCase = Depends(
        inject_use_case(container.learning.create_flashcard_for_book_use_case)
    ),
) -> FlashcardCreateResponse:
    """
    Create a standalone flashcard for a book (without a highlight).

    This creates a flashcard that is associated with a book but not tied
    to any specific highlight.

    Args:
        book_id: ID of the book
        request: Request containing question and answer
        use_case: FlashcardUseCase injected via dependency container

    Returns:
        Created flashcard

    Raises:
        HTTPException: If book not found or creation fails
    """
    flashcard_entity = await use_case.create_flashcard(
        book_id=book_id,
        user_id=current_user.id.value,
        question=request.question,
        answer=request.answer,
        chapter_id=request.chapter_id,
    )
    # Manually construct Pydantic schema from domain entity
    flashcard = Flashcard(
        id=flashcard_entity.id.value,
        user_id=flashcard_entity.user_id.value,
        book_id=flashcard_entity.book_id.value,
        highlight_id=flashcard_entity.highlight_id.value if flashcard_entity.highlight_id else None,
        chapter_id=flashcard_entity.chapter_id.value if flashcard_entity.chapter_id else None,
        question=flashcard_entity.question,
        answer=flashcard_entity.answer,
    )
    return FlashcardCreateResponse(
        success=True,
        message="Flashcard created successfully",
        flashcard=flashcard,
    )


@router.get(
    "/{book_id}/flashcards",
    response_model=CollectionResponse[FlashcardWithHighlight],
    status_code=status.HTTP_200_OK,
)
async def get_flashcards_for_book(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetFlashcardsByBookUseCase = Depends(
        inject_use_case(container.learning.get_flashcards_by_book_use_case)
    ),
) -> CollectionResponse[FlashcardWithHighlight]:
    """
    Get all flashcards for a book with embedded highlight data.

    Returns all flashcards ordered by creation date (newest first).

    Args:
        book_id: ID of the book
        use_case: FlashcardUseCase injected via dependency container

    Returns:
        List of flashcards with highlight data for the book

    Raises:
        HTTPException: If book not found or fetching fails
    """
    view = await use_case.get_flashcards(book_id, current_user.id.value)
    return CollectionResponse[FlashcardWithHighlight](
        items=[_flashcard_schema(card) for card in view]
    )


def _highlight_schema(view: FlashcardHighlightView) -> HighlightResponseBase:
    """Render the highlight embedded in a flashcard row."""
    return HighlightResponseBase(
        id=view.id,
        book_id=view.book_id,
        chapter_id=view.chapter_id,
        text=view.text,
        page=view.page,
        datetime=view.datetime,
        chapter=view.chapter_name,
        chapter_number=view.chapter_number,
        label=HighlightLabel(
            highlight_style_id=view.label.highlight_style_id,
            text=view.label.text,
            ui_color=view.label.ui_color,
        )
        if view.label
        else None,
        created_at=view.created_at,
        updated_at=view.updated_at,
        tags=[
            TagInBook(id=tag.id, name=tag.name, tag_group_id=tag.tag_group_id) for tag in view.tags
        ],
    )


def _flashcard_schema(view: FlashcardWithHighlightView) -> FlashcardWithHighlight:
    """Render one flashcard row of the book's flashcard list."""
    return FlashcardWithHighlight(
        id=view.id,
        user_id=view.user_id,
        book_id=view.book_id,
        highlight_id=view.highlight_id,
        chapter_id=view.chapter_id,
        note_id=view.note_id,
        question=view.question,
        answer=view.answer,
        highlight=_highlight_schema(view.highlight) if view.highlight else None,
    )
