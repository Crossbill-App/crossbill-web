"""Read use case behind the reading-position endpoint."""

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.web_reader.protocols.web_reading_position_repository import (
    WebReadingPositionRepositoryProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition


class GetReadingPositionUseCase:
    """Serve a book's stored web-reader position, so the browser can resume from it.

    Small enough not to deserve a port of its own -- it reads one row by its
    natural key -- so it delegates to the repository and hands back the domain
    entity, the "halfway option" of ADR-0001.

    Nothing is written here. A reading session that has stopped being extended
    is already over (ADR-0004, Amendment 3), so there is no idle session for a
    read to have to close.
    """

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        position_repository: WebReadingPositionRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.position_repository = position_repository

    async def get_reading_position(self, book_id: int, user_id: int) -> WebReadingPosition | None:
        """Return where the reader last was in this book, or ``None`` if never here.

        The book is looked up first so that "this book is not yours" stays a
        404, as it is everywhere else in the library, rather than reading as a
        book nobody has opened yet.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        book = await self.book_repository.find_by_id(BookId(book_id), UserId(user_id))
        if book is None:
            raise BookNotFoundError(book_id)
        return await self.position_repository.find_for_book(BookId(book_id), UserId(user_id))
