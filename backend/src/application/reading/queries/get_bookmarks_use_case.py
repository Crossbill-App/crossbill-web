"""Read use case for a book's bookmark list."""

from src.application.common.queries.refs import BookmarkView
from src.application.reading.queries.bookmarks import BookmarkQueryProtocol
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetBookmarksUseCase:
    """Serve the bookmark list for a book."""

    def __init__(self, bookmark_query: BookmarkQueryProtocol) -> None:
        self.bookmark_query = bookmark_query

    async def get_bookmarks_by_book(self, book_id: int, user_id: int) -> tuple[BookmarkView, ...]:
        """Return the book's bookmarks, newest first.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        bookmarks = await self.bookmark_query.list_for_book(BookId(book_id), UserId(user_id))
        if bookmarks is None:
            raise BookNotFoundError(book_id)
        return bookmarks
