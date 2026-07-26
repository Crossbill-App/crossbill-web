from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.reading.queries.get_bookmarks_use_case import (
    GetBookmarksUseCase,
)
from src.application.reading.use_cases.bookmarks.create_bookmark_use_case import (
    CreateBookmarkUseCase,
)
from src.application.reading.use_cases.bookmarks.delete_bookmark_use_case import (
    DeleteBookmarkUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.schemas import Bookmark, BookmarkCreateRequest

router = APIRouter(prefix="/books", tags=["bookmarks"])


@router.post(
    "/{book_id}/bookmarks",
    response_model=Bookmark,
    status_code=status.HTTP_201_CREATED,
)
async def create_bookmark(
    book_id: int,
    request: BookmarkCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CreateBookmarkUseCase = Depends(
        inject_use_case(container.reading.create_bookmark_use_case)
    ),
) -> Bookmark:
    """
    Create a bookmark for a highlight in a book.

    Bookmarks allow users to track their reading progress by marking specific
    highlights they want to return to later.

    Args:
        book_id: ID of the book
        request: Request containing the highlight_id to bookmark
        use_case: BookmarkService injected via dependency container

    Returns:
        Created Bookmark

    Raises:
        HTTPException: If book or highlight not found, or creation fails
    """
    bookmark = await use_case.create_bookmark(book_id, request.highlight_id, current_user.id.value)

    return Bookmark(
        id=bookmark.id.value,
        book_id=bookmark.book_id.value,
        highlight_id=bookmark.highlight_id.value,
        created_at=bookmark.created_at,
    )


@router.delete(
    "/{book_id}/bookmarks/{bookmark_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_bookmark(
    book_id: int,
    bookmark_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: DeleteBookmarkUseCase = Depends(
        inject_use_case(container.reading.delete_bookmark_use_case)
    ),
) -> None:
    """
    Delete a bookmark from a book.

    This operation is idempotent - calling it on a non-existent bookmark
    will succeed and return 200 without error.

    Args:
        book_id: ID of the book
        bookmark_id: ID of the bookmark to delete
        use_case: BookmarkService injected via dependency container

    Raises:
        HTTPException: If book not found or deletion fails
    """
    await use_case.delete_bookmark(book_id, bookmark_id, current_user.id.value)


@router.get(
    "/{book_id}/bookmarks",
    response_model=CollectionResponse[Bookmark],
    status_code=status.HTTP_200_OK,
)
async def get_bookmarks(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetBookmarksUseCase = Depends(
        inject_use_case(container.reading.get_bookmarks_use_case)
    ),
) -> CollectionResponse[Bookmark]:
    """
    Get all bookmarks for a book.

    Returns all bookmarks ordered by creation date (newest first).

    Args:
        book_id: ID of the book
        use_case: BookmarkService injected via dependency container

    Returns:
        List of bookmarks for the book

    Raises:
        HTTPException: If book not found or fetching fails
    """
    bookmarks = await use_case.get_bookmarks_by_book(book_id, current_user.id.value)

    bookmark_schemas = [
        Bookmark(
            id=b.id,
            book_id=b.book_id,
            highlight_id=b.highlight_id,
            created_at=b.created_at,
        )
        for b in bookmarks
    ]
    return CollectionResponse[Bookmark](items=bookmark_schemas)
