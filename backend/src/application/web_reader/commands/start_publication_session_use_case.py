"""Mint the credential a navigator's iframe can carry, for one user and one book."""

from datetime import datetime

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.web_reader.dtos import PublicationToken
from src.application.web_reader.protocols.publication_token_service import (
    PublicationTokenServiceProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class StartPublicationSessionUseCase:
    """Hand a user a publication token for a book they own."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        publication_token_service: PublicationTokenServiceProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.publication_token_service = publication_token_service

    async def start_publication_session(
        self, book_id: int, user_id: int, not_after: datetime
    ) -> PublicationToken:
        """Mint a token for this user's book, expiring at ``not_after`` at the latest.

        Ownership is the whole check: whether there is anything to read is the
        manifest request's answer, not this one's.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        book = await self.book_repository.find_by_id(BookId(book_id), UserId(user_id))
        if book is None:
            raise BookNotFoundError(book_id)
        return self.publication_token_service.create_publication_token(
            user_id=user_id, book_id=book_id, not_after=not_after
        )
