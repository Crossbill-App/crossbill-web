from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.application.library.use_cases.book_management.delete_book_use_case import (
    DeleteBookUseCase,
)
from src.application.library.use_cases.book_management.get_book_details_use_case import (
    GetBookDetailsUseCase,
)
from src.application.library.use_cases.book_management.update_reading_stage_use_case import (
    UpdateReadingStageUseCase,
)
from src.application.library.use_cases.book_queries.get_books_with_counts_use_case import (
    GetBooksWithCountsUseCase,
)
from src.application.library.use_cases.book_queries.get_recently_viewed_books_use_case import (
    GetRecentlyViewedBooksUseCase,
)
from src.core import container
from src.domain.identity import User
from src.domain.library.services.book_details_aggregator import BookDetailsAggregation
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse, PaginatedResponse
from src.infrastructure.common.schemas.position_schemas import PositionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import Flashcard
from src.infrastructure.library.schemas import (
    BookWithHighlightCount,
)
from src.infrastructure.library.schemas.book_schemas import BookReadingStageUpdateRequest
from src.infrastructure.reading.schema_mappers import map_chapters_to_schemas
from src.infrastructure.reading.schemas import (
    BookDetails,
    Bookmark,
)
from src.infrastructure.tagging.schemas import TagGroupInBook, TagInBook

router = APIRouter(prefix="/books", tags=["books"])


def _build_book_details_schema(
    agg: BookDetailsAggregation,
    labels: dict[int, ResolvedLabel] | None = None,
) -> BookDetails:
    """
    Build BookDetails Pydantic schema from BookDetailsAggregation.

    Args:
        agg: BookDetailsAggregation domain dataclass
        labels: Optional dict mapping highlight_style_id -> ResolvedLabel

    Returns:
        BookDetails Pydantic schema
    """
    return BookDetails(
        id=agg.book.id.value,
        client_book_id=agg.book.client_book_id,
        title=agg.book.title,
        author=agg.book.author,
        isbn=agg.book.isbn,
        cover_file=agg.book.cover_file,
        cover_blurhash=agg.book.cover_blurhash,
        description=agg.book.description,
        language=agg.book.language,
        page_count=agg.book.page_count,
        reading_stage=agg.book.reading_stage.value if agg.book.reading_stage else None,
        tags=[
            TagInBook(
                id=tag.id.value,
                name=tag.name,
                tag_group_id=tag.tag_group_id,
            )
            for tag in agg.tags
        ],
        tag_groups=[
            TagGroupInBook(
                id=group.id.value,
                name=group.name,
            )
            for group in agg.tag_groups
        ],
        bookmarks=[
            Bookmark(
                id=b.id.value,
                book_id=b.book_id.value,
                highlight_id=b.highlight_id.value,
                created_at=b.created_at,
            )
            for b in agg.bookmarks
        ],
        book_flashcards=[
            Flashcard(
                id=f.id.value,
                user_id=f.user_id.value,
                book_id=f.book_id.value,
                highlight_id=None,
                chapter_id=f.chapter_id.value if f.chapter_id else None,
                question=f.question,
                answer=f.answer,
            )
            for f in agg.book_flashcards
        ],
        chapters=map_chapters_to_schemas(agg.chapters_with_highlights, labels),
        reading_position=PositionResponse(
            index=agg.reading_position.index,
            char_index=agg.reading_position.char_index,
        )
        if agg.reading_position
        else None,
        end_position=PositionResponse(
            index=agg.book.end_position.index,
            char_index=agg.book.end_position.char_index,
        )
        if agg.book.end_position
        else None,
        created_at=agg.book.created_at,
        updated_at=agg.book.updated_at,
        last_viewed=agg.book.last_viewed,
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
    results, total = await use_case.get_books_with_counts(
        current_user.id.value, offset, limit, only_with_flashcards, search
    )

    books_list = [
        BookWithHighlightCount(
            id=book.id.value,
            client_book_id=book.client_book_id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            cover_file=book.cover_file,
            cover_blurhash=book.cover_blurhash,
            description=book.description,
            language=book.language,
            page_count=book.page_count,
            highlight_count=highlight_count,
            flashcard_count=flashcard_count,
            end_position=PositionResponse(
                index=book.end_position.index,
                char_index=book.end_position.char_index,
            )
            if book.end_position
            else None,
            created_at=book.created_at,
            updated_at=book.updated_at,
            last_viewed=book.last_viewed,
        )
        for book, highlight_count, flashcard_count in results
    ]

    return PaginatedResponse[BookWithHighlightCount](
        items=books_list, total=total, offset=offset, limit=limit
    )


@router.get(
    "/recently-viewed",
    response_model=CollectionResponse[BookWithHighlightCount],
    status_code=status.HTTP_200_OK,
)
async def get_recently_viewed_books(
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetRecentlyViewedBooksUseCase = Depends(
        inject_use_case(container.library.get_recently_viewed_books_use_case)
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of books to return"),
) -> CollectionResponse[BookWithHighlightCount]:
    """
    Get recently viewed books with their highlight counts.

    Returns books that have been viewed at least once, ordered by most recently viewed.

    Args:
        limit: Maximum number of books to return (default: 10, max: 50)

    Returns:
        CollectionResponse with list of recently viewed books

    Raises:
        HTTPException: If fetching books fails due to server error
    """
    results = await use_case.get_recently_viewed(current_user.id.value, limit)

    books_list = [
        BookWithHighlightCount(
            id=book.id.value,
            client_book_id=book.client_book_id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            cover_file=book.cover_file,
            cover_blurhash=book.cover_blurhash,
            description=book.description,
            language=book.language,
            page_count=book.page_count,
            highlight_count=highlight_count,
            flashcard_count=flashcard_count,
            end_position=PositionResponse(
                index=book.end_position.index,
                char_index=book.end_position.char_index,
            )
            if book.end_position
            else None,
            created_at=book.created_at,
            updated_at=book.updated_at,
            last_viewed=book.last_viewed,
        )
        for book, highlight_count, flashcard_count in results
    ]

    return CollectionResponse[BookWithHighlightCount](items=books_list)


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
    agg = await use_case.get_book_details(book_id, current_user.id.value)
    return _build_book_details_schema(agg, agg.labels)


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
