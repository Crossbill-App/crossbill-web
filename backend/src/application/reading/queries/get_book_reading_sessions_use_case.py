"""Read use case for a book's reading-session list."""

from src.application.reading.queries.reading_sessions import (
    ReadingSessionPageView,
    ReadingSessionQueryProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class ReadingSessionQueryUseCase:
    """Serve a page of a book's reading sessions."""

    def __init__(self, reading_session_query: ReadingSessionQueryProtocol) -> None:
        self.reading_session_query = reading_session_query

    async def get_sessions_for_book(
        self, book_id: int, user_id: int, limit: int, offset: int
    ) -> ReadingSessionPageView:
        """Return the requested page of sessions, newest first.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        page = await self.reading_session_query.list_for_book(
            BookId(book_id), UserId(user_id), limit, offset
        )
        if page is None:
            raise BookNotFoundError(book_id)
        return page
