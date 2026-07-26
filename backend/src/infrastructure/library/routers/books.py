from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.application.library.queries.book_details import (
    BookDetailsQueryProtocol,
    BookDetailsView,
    ChapterWithHighlightsView,
    HighlightView,
)
from src.application.library.use_cases.book_management.delete_book_use_case import (
    DeleteBookUseCase,
)
from src.application.library.use_cases.book_management.mark_book_viewed_use_case import (
    MarkBookViewedUseCase,
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
from src.domain.common.value_objects import BookId, UserId
from src.domain.identity import User
from src.domain.reading.exceptions import BookNotFoundError
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse, PaginatedResponse
from src.infrastructure.common.schemas.position_schemas import PositionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import Flashcard
from src.infrastructure.library.schemas import (
    BookWithHighlightCount,
)
from src.infrastructure.library.schemas.book_schemas import BookReadingStageUpdateRequest
from src.infrastructure.reading.schemas import (
    BookDetails,
    Bookmark,
    ChapterWithHighlights,
    Highlight,
    HighlightLabel,
)
from src.infrastructure.tagging.schemas import TagGroupInBook, TagInBook

router = APIRouter(prefix="/books", tags=["books"])


def _build_highlight_schema(highlight: HighlightView) -> Highlight:
    """Build the Highlight schema from a highlight in the book-details read model."""
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
        highlights=[_build_highlight_schema(highlight) for highlight in chapter.highlights],
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
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
                question=f.question,
                answer=f.answer,
            )
            for f in view.book_flashcards
        ],
        chapters=[_build_chapter_schema(chapter) for chapter in view.chapters],
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
    mark_viewed: MarkBookViewedUseCase = Depends(
        inject_use_case(container.library.mark_book_viewed_use_case)
    ),
    query: BookDetailsQueryProtocol = Depends(
        inject_use_case(container.library.book_details_query)
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
    # Opening the page stamps the book as viewed. That is a command, so it runs
    # through its own use case before the read model is queried.
    await mark_viewed.mark_viewed(book_id, current_user.id.value)

    view = await query.get_book_details(BookId(book_id), UserId(current_user.id.value))
    if view is None:
        raise BookNotFoundError(book_id)
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
