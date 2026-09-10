"""Web reader domain exceptions."""

from src.domain.common.exceptions import DomainError, EntityNotFoundError


class PublicationResourceNotFoundError(EntityNotFoundError):
    """Raised when a publication does not contain the requested file."""

    def __init__(self, path: str) -> None:
        super().__init__("Publication resource", path)


class PublicationIndexUnavailableError(DomainError):
    """Raised when a book's index cannot be read back after being derived.

    Deriving an index stores it best-effort, so a failed write leaves a book
    that exists but has nothing to serve from -- a server fault, not a 404.
    """

    def __init__(self, book_id: int) -> None:
        super().__init__(f"No publication index could be stored for book {book_id}")
