"""API routes for highlights management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.application.reading.commands.highlights.highlight_delete_use_case import (
    HighlightDeleteUseCase,
)
from src.application.reading.commands.highlights.highlight_upload_use_case import (
    HighlightUploadData,
    HighlightUploadUseCase,
)
from src.application.reading.queries.highlight_search import (
    SearchChapterView,
    SearchHighlightView,
)
from src.application.reading.queries.highlight_search_use_case import (
    HighlightSearchUseCase,
)
from src.core import container
from src.domain.identity.entities.user import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.learning.schemas import Flashcard
from src.infrastructure.reading.schemas import (
    BookHighlightSearchResponse,
    ChapterWithHighlights,
    Highlight,
    HighlightDeleteRequest,
    HighlightDeleteResponse,
    HighlightLabel,
    HighlightUploadRequest,
    HighlightUploadResponse,
)
from src.infrastructure.tagging.schemas import TagInBook

router = APIRouter(prefix="", tags=["highlights"])


def _build_highlight_schema(highlight: SearchHighlightView) -> Highlight:
    """Build the Highlight schema from a match in the search read model."""
    return Highlight(
        id=highlight.id,
        book_id=highlight.book_id,
        chapter_id=highlight.chapter_id,
        text=highlight.text,
        chapter=highlight.chapter_name,
        chapter_number=highlight.chapter_number,
        page=highlight.page,
        datetime=highlight.datetime,
        label=HighlightLabel(
            highlight_style_id=highlight.label.highlight_style_id,
            text=highlight.label.text,
            ui_color=highlight.label.ui_color,
        )
        if highlight.label
        else None,
        flashcards=[
            Flashcard(
                id=card.id,
                user_id=card.user_id,
                book_id=card.book_id,
                highlight_id=card.highlight_id,
                chapter_id=card.chapter_id,
                question=card.question,
                answer=card.answer,
            )
            for card in highlight.flashcards
        ],
        tags=[
            TagInBook(id=tag.id, name=tag.name, tag_group_id=tag.tag_group_id)
            for tag in highlight.tags
        ],
        created_at=highlight.created_at,
        updated_at=highlight.updated_at,
    )


def _build_chapter_schema(chapter: SearchChapterView) -> ChapterWithHighlights:
    """Build the ChapterWithHighlights schema from the search read model.

    Search rows carry no parent chapter or start position, and never have.
    """
    return ChapterWithHighlights(
        id=chapter.id,
        name=chapter.name,
        chapter_number=chapter.chapter_number,
        parent_id=None,
        start_position=None,
        highlights=[_build_highlight_schema(highlight) for highlight in chapter.highlights],
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )


@router.post(
    "/highlights/upload",
    response_model=HighlightUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_highlights(
    request: HighlightUploadRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: HighlightUploadUseCase = Depends(
        inject_use_case(container.reading.highlight_upload_use_case)
    ),
) -> HighlightUploadResponse:
    """
    Upload highlights from KOReader.

    Creates or updates book record and adds highlights with automatic deduplication.
    Duplicates are identified by the combination of book, text, and datetime.

    Args:
        request: Highlight upload request containing book metadata and highlights

    Returns:
        HighlightUploadResponse with upload statistics

    Raises:
        HTTPException: If upload fails due to server error
    """
    highlight_data_list = [
        HighlightUploadData(
            text=h.text,
            chapter_number=h.chapter_number,
            chapter=h.chapter,
            start_xpoint=h.start_xpoint,
            end_xpoint=h.end_xpoint,
            page=h.page,
            color=h.color,
            drawer=h.drawer,
        )
        for h in request.highlights
    ]

    created, skipped = await use_case.upload_highlights(
        client_book_id=request.client_book_id,
        highlight_data_list=highlight_data_list,
        user_id=current_user.id.value,
    )

    return HighlightUploadResponse(
        success=True,
        message="Successfully synced highlights",
        book_id=0,  # TODO: Return actual book_id from service if needed
        highlights_created=created,
        highlights_skipped=skipped,
    )


@router.get(
    "/books/{book_id}/highlights",
    response_model=BookHighlightSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def search_book_highlights(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    search_text: str = Query(
        ...,
        alias="searchText",
        min_length=1,
        description="Text to search for in highlights",
    ),
    use_case: HighlightSearchUseCase = Depends(
        inject_use_case(container.reading.highlight_search_use_case)
    ),
) -> BookHighlightSearchResponse:
    """
    Search for highlights in book using full-text search.

    Searches across all highlight text using PostgreSQL full-text search.
    Results are ranked by relevance and excludes soft-deleted highlights.
    """
    view = await use_case.search_book_highlights(book_id, current_user.id.value, search_text)
    return BookHighlightSearchResponse(
        chapters=[_build_chapter_schema(chapter) for chapter in view.chapters],
        total=view.total,
    )


@router.delete(
    "/books/{book_id}/highlight",
    response_model=HighlightDeleteResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_highlights(
    book_id: int,
    request: HighlightDeleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: HighlightDeleteUseCase = Depends(
        inject_use_case(container.reading.highlight_delete_use_case)
    ),
) -> HighlightDeleteResponse:
    """
    Soft delete highlights from a book.

    This performs a soft delete by marking the highlights as deleted.
    When syncing highlights, deleted highlights will not be recreated,
    ensuring that user deletions persist across syncs.

    Args:
        book_id: ID of the book
        request: Request containing list of highlight IDs to delete

    Returns:
        HighlightDeleteResponse with deletion status and count

    Raises:
        HTTPException: If book is not found or deletion fails
        :param use_case:
    """
    deleted_count = await use_case.delete_highlights(
        book_id, request.highlight_ids, current_user.id.value
    )
    return HighlightDeleteResponse(
        success=True,
        message=f"Successfully deleted {deleted_count} highlight(s)",
        deleted_count=deleted_count,
    )
