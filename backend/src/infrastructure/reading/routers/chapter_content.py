"""API router for chapter text content extraction."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.reading.queries.chapter_content_use_case import (
    ChapterContentUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.schemas.chapter_content_schemas import (
    ChapterContentResponse,
)

router = APIRouter(prefix="/chapters", tags=["chapters"])


@router.get(
    "/{chapter_id}/content",
    response_model=ChapterContentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_chapter_content(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: ChapterContentUseCase = Depends(
        inject_use_case(container.reading.chapter_content_use_case)
    ),
) -> ChapterContentResponse:
    """Get the full text content of a chapter from the EPUB file."""
    content, chapter_name, book_id = await use_case.get_chapter_content(
        chapter_id=chapter_id,
        user_id=current_user.id.value,
    )

    return ChapterContentResponse(
        chapter_id=chapter_id,
        chapter_name=chapter_name,
        book_id=book_id,
        content=content,
    )
