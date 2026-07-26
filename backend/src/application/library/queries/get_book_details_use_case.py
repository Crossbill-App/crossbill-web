"""Read use case for the book-details view.

Read use cases live in the ``queries`` package rather than in ``use_cases``:
``use_cases`` holds commands only, and the ``queries-are-dead-ends`` import
contract forbids commands from importing read models. Wrapping the query port
is deliberate boilerplate -- routers invoke use cases, never ports.
"""

from src.application.library.commands.book_management.mark_book_viewed_use_case import (
    MarkBookViewedUseCase,
)
from src.application.library.queries.book_details import (
    BookDetailsQueryProtocol,
    BookDetailsView,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetBookDetailsUseCase:
    """Serve the book-details view, recording the visit on the way."""

    def __init__(
        self,
        mark_book_viewed_use_case: MarkBookViewedUseCase,
        book_details_query: BookDetailsQueryProtocol,
    ) -> None:
        self.mark_book_viewed_use_case = mark_book_viewed_use_case
        self.book_details_query = book_details_query

    async def get_book_details(self, book_id: int, user_id: int) -> BookDetailsView:
        """Return the book-details view, stamping the book as viewed first.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        await self.mark_book_viewed_use_case.mark_viewed(book_id, user_id)

        view = await self.book_details_query.get_book_details(BookId(book_id), UserId(user_id))
        if view is None:
            raise BookNotFoundError(book_id)
        return view
