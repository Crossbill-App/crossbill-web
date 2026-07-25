from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.learning.use_cases.flashcards.create_flashcard_for_book_use_case import (
    CreateFlashcardForBookUseCase,
)
from src.application.learning.use_cases.flashcards.get_flashcards_by_book_use_case import (
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
    # Get flashcards with highlights from use case (returns DTOs + labels)
    flashcards_with_highlights, labels = await use_case.get_flashcards(
        book_id, current_user.id.value
    )

    # Convert DTOs to Pydantic schemas
    flashcards = []
    for dto in flashcards_with_highlights:
        fc = dto.flashcard
        highlight = dto.highlight
        chapter = dto.chapter
        tags = dto.tags

        # Convert highlight to Pydantic schema if present
        highlight_schema = None
        if highlight:
            resolved = (
                labels.get(highlight.highlight_style_id.value)
                if highlight.highlight_style_id
                else None
            )
            # Manually construct highlight schema
            highlight_schema = HighlightResponseBase(
                id=highlight.id.value,
                book_id=highlight.book_id.value,
                chapter_id=highlight.chapter_id.value if highlight.chapter_id else None,
                text=highlight.text,
                page=highlight.page,
                datetime=highlight.datetime,
                chapter=chapter.name if chapter else None,
                chapter_number=chapter.chapter_number if chapter else None,
                label=HighlightLabel(
                    highlight_style_id=highlight.highlight_style_id.value
                    if highlight.highlight_style_id
                    else None,
                    text=resolved.label if resolved else None,
                    ui_color=resolved.ui_color if resolved else None,
                )
                if highlight.highlight_style_id
                else None,
                created_at=highlight.created_at,
                updated_at=highlight.updated_at,
                tags=[
                    TagInBook(
                        id=tag.id.value,
                        name=tag.name,
                        tag_group_id=tag.tag_group_id,
                    )
                    for tag in tags
                ],
            )

        # Construct flashcard schema with highlight
        flashcard_schema = FlashcardWithHighlight(
            id=fc.id.value,
            user_id=fc.user_id.value,
            book_id=fc.book_id.value,
            highlight_id=fc.highlight_id.value if fc.highlight_id else None,
            chapter_id=fc.chapter_id.value if fc.chapter_id else None,
            question=fc.question,
            answer=fc.answer,
            highlight=highlight_schema,
        )
        flashcards.append(flashcard_schema)

    return CollectionResponse[FlashcardWithHighlight](items=flashcards)
