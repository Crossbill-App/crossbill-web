from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.application.library.commands.book_management.delete_book_use_case import (
    DeleteBookUseCase,
)
from src.application.library.commands.book_management.update_book_use_case import (
    UpdateBookUseCase,
)
from src.application.library.commands.book_management.update_reading_stage_use_case import (
    UpdateReadingStageUseCase,
)
from src.application.library.queries.book_details import (
    BookDetailsView,
    ChapterWithHighlightsView,
)
from src.application.library.queries.book_list import BookWithCountsView
from src.application.library.queries.get_book_details_use_case import GetBookDetailsUseCase
from src.application.library.queries.get_books_with_counts_use_case import (
    GetBooksWithCountsUseCase,
)
from src.application.library.queries.get_recent_books_use_case import (
    GetRecentBooksUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse, PaginatedResponse
from src.infrastructure.common.schemas.position_schemas import PositionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import Flashcard
from src.infrastructure.library.schemas import (
    BookWithHighlightCount,
)
from src.infrastructure.library.schemas.book_schemas import (
    BookReadingStageUpdateRequest,
    BookUpdateRequest,
)
from src.infrastructure.reading.schemas import (
    BookDetails,
    Bookmark,
    ChapterWithHighlights,
)
from src.infrastructure.reading.schemas.highlight_builders import build_highlight_schema
from src.infrastructure.tagging.schemas import TagGroupInBook, TagInBook

router = APIRouter(prefix="/books", tags=["books"])


def _build_chapter_schema(chapter: ChapterWithHighlightsView) -> ChapterWithHighlights:
    """Build the ChapterWithHighlights schema from the book-details read model."""
    return ChapterWithHighlights(
        id=chapter.id,
        name=chapter.name,
        chapter_number=chapter.chapter_number,
        parent_id=chapter.parent_id,
        start_position=PositionResponse(
            index=chapter.start_position.index,
            char_index=chapter.start_position.char_index,
        )
        if chapter.start_position
        else None,
        highlights=[build_highlight_schema(highlight) for highlight in chapter.highlights],
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )


def _build_book_with_counts_schema(view: BookWithCountsView) -> BookWithHighlightCount:
    """Build the list-row schema shared by the library and recent-books lists."""
    return BookWithHighlightCount(
        id=view.id,
        client_book_id=view.client_book_id,
        title=view.title,
        author=view.author,
        isbn=view.isbn,
        cover_file=view.cover_file,
        cover_blurhash=view.cover_blurhash,
        description=view.description,
        language=view.language,
        page_count=view.page_count,
        highlight_count=view.highlight_count,
        flashcard_count=view.flashcard_count,
        note_count=view.note_count,
        reading_stage=view.reading_stage.value if view.reading_stage else None,
        end_position=PositionResponse(
            index=view.end_position.index,
            char_index=view.end_position.char_index,
        )
        if view.end_position
        else None,
        created_at=view.created_at,
        updated_at=view.updated_at,
        last_viewed=view.last_viewed,
        last_synced=view.last_synced,
    )


def _build_book_details_schema(view: BookDetailsView) -> BookDetails:
    """
    Build BookDetails Pydantic schema from the book-details read model.

    Args:
        view: BookDetailsView returned by the book-details query service

    Returns:
        BookDetails Pydantic schema
    """
    return BookDetails(
        id=view.id,
        client_book_id=view.client_book_id,
        title=view.title,
        author=view.author,
        isbn=view.isbn,
        cover_file=view.cover_file,
        cover_blurhash=view.cover_blurhash,
        description=view.description,
        language=view.language,
        page_count=view.page_count,
        reading_stage=view.reading_stage.value if view.reading_stage else None,
        tags=[
            TagInBook(
                id=tag.id,
                name=tag.name,
                tag_group_id=tag.tag_group_id,
            )
            for tag in view.tags
        ],
        tag_groups=[
            TagGroupInBook(
                id=group.id,
                name=group.name,
            )
            for group in view.tag_groups
        ],
        bookmarks=[
            Bookmark(
                id=b.id,
                book_id=b.book_id,
                highlight_id=b.highlight_id,
                created_at=b.created_at,
            )
            for b in view.bookmarks
        ],
        book_flashcards=[
            Flashcard(
                id=f.id,
                user_id=f.user_id,
                book_id=f.book_id,
                highlight_id=None,
                chapter_id=f.chapter_id,
                note_id=f.note_id,
                question=f.question,
                answer=f.answer,
            )
            for f in view.book_flashcards
        ],
        chapters=[_build_chapter_schema(chapter) for chapter in view.chapters],
        highlight_count=view.highlight_count,
        reading_position=PositionResponse(
            index=view.reading_position.index,
            char_index=view.reading_position.char_index,
        )
        if view.reading_position
        else None,
        end_position=PositionResponse(
            index=view.end_position.index,
            char_index=view.end_position.char_index,
        )
        if view.end_position
        else None,
        created_at=view.created_at,
        updated_at=view.updated_at,
        last_viewed=view.last_viewed,
    )


@router.get(
    "/",
    response_model=PaginatedResponse[BookWithHighlightCount],
    status_code=status.HTTP_200_OK,
)
async def get_books(
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetBooksWithCountsUseCase = Depends(
        inject_use_case(container.library.get_books_with_counts_use_case)
    ),
    offset: int = Query(0, ge=0, description="Number of books to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of books to return"),
    only_with_flashcards: bool = Query(False, description="Return only books with flashcards"),
    search: str | None = Query(None, description="Search text to filter books by title or author"),
) -> PaginatedResponse[BookWithHighlightCount]:
    """
    Get all books with their highlight counts, sorted alphabetically by title.

    Args:
        offset: Number of books to skip (for pagination)
        limit: Maximum number of books to return (for pagination)
        search: Optional search text to filter books by title or author

    Returns:
        PaginatedResponse with list of books and pagination info

    Raises:
        HTTPException: If fetching books fails due to server error
    """
    page = await use_case.get_books_with_counts(
        current_user.id.value, offset, limit, only_with_flashcards, search
    )

    return PaginatedResponse[BookWithHighlightCount](
        items=[_build_book_with_counts_schema(book) for book in page.books],
        total=page.total,
        offset=offset,
        limit=limit,
    )


# Declared before "/{book_id}" so the literal path wins the match.
@router.get(
    "/recent",
    response_model=CollectionResponse[BookWithHighlightCount],
    status_code=status.HTTP_200_OK,
)
async def get_recent_books(
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetRecentBooksUseCase = Depends(
        inject_use_case(container.library.get_recent_books_use_case)
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of books to return"),
) -> CollectionResponse[BookWithHighlightCount]:
    """
    Get the user's most recently touched books, with their counts.

    Returns books the user has opened or an e-reader has sent highlights or
    reading sessions for, ordered by the later of those two timestamps. A book
    that has been neither opened nor synced is left out.

    Args:
        limit: Maximum number of books to return (default: 10, max: 50)

    Returns:
        CollectionResponse with list of recent books

    Raises:
        HTTPException: If fetching books fails due to server error
    """
    books = await use_case.get_recent(current_user.id.value, limit)

    return CollectionResponse[BookWithHighlightCount](
        items=[_build_book_with_counts_schema(book) for book in books]
    )


@router.get("/{book_id}", response_model=BookDetails, status_code=status.HTTP_200_OK)
async def get_book_details(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetBookDetailsUseCase = Depends(
        inject_use_case(container.library.get_book_details_use_case)
    ),
) -> BookDetails:
    """
    Get detailed information about a book including its chapters and highlights.

    Args:
        book_id: ID of the book to retrieve

    Returns:
        BookDetails with chapters and their highlights

    Raises:
        HTTPException: If book is not found or fetching fails
    """
    view = await use_case.get_book_details(book_id, current_user.id.value)
    return _build_book_details_schema(view)


@router.put("/{book_id}/reading-stage", status_code=status.HTTP_204_NO_CONTENT)
async def update_reading_stage(
    book_id: int,
    request: BookReadingStageUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: UpdateReadingStageUseCase = Depends(
        inject_use_case(container.library.update_reading_stage_use_case)
    ),
) -> None:
    """Set or clear the manual reading stage on a book."""
    await use_case.update_reading_stage(
        book_id=book_id,
        user_id=current_user.id.value,
        reading_stage=request.reading_stage,
    )


@router.patch("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_book(
    book_id: int,
    request: BookUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: UpdateBookUseCase = Depends(inject_use_case(container.library.update_book_use_case)),
) -> None:
    """Apply the reader's edits to a book.

    Partial by contract: only fields present in the request body are applied,
    which is why this reads `model_fields_set` rather than the parsed values.
    """
    if "description" in request.model_fields_set:
        await use_case.update_description(
            book_id=book_id,
            user_id=current_user.id.value,
            description=request.description,
        )


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: DeleteBookUseCase = Depends(inject_use_case(container.library.delete_book_use_case)),
) -> None:
    """
    Delete a book and all its contents (hard delete).

    This will permanently delete the book, all its chapters, and all its highlights.
    If the user syncs highlights from the book again, it will recreate the book,
    chapters, and highlights.

    Args:
        book_id: ID of the book to delete

    Raises:
        HTTPException: If book is not found or deletion fails
    """
    await use_case.delete_book(book_id, current_user.id.value)
