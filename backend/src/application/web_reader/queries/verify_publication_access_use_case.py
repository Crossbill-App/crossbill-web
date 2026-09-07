"""The read behind the publication session endpoint: may this user read this book?

Small enough not to deserve a port of its own, so it delegates straight to the
book repository -- the "halfway option" of
``docs/adr/0001-read-models-and-query-services.md``. It is a query in the sense
that matters: it reads, it writes nothing, and what it produces (a credential,
built by the router) never comes back in as a command.
"""

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class VerifyPublicationAccessUseCase:
    """Assert that a user may read a book's publication, before they are given a cookie for it."""

    def __init__(self, book_repository: BookRepositoryProtocol) -> None:
        self.book_repository = book_repository

    async def verify_publication_access(self, book_id: int, user_id: int) -> None:
        """Check that the book is this user's.

        Nothing is read out of the EPUB: the credential says who may look, and
        whether there is anything to look at is the reading endpoints' answer to
        give. A book with no stored file still gets a session and still answers
        404 on the manifest, which keeps the two questions apart.

        Raises:
            BookNotFoundError: If the user has no such book -- 404 rather than
                403, as everywhere else in the library: whether the book exists
                is its owner's business.
        """
        book = await self.book_repository.find_by_id(BookId(book_id), UserId(user_id))
        if book is None:
            raise BookNotFoundError(book_id)
