"""Web reader domain exceptions."""

from src.domain.common.exceptions import DomainError, EntityNotFoundError


class PublicationResourceNotFoundError(EntityNotFoundError):
    """Raised when a publication does not contain the requested file."""

    def __init__(self, path: str) -> None:
        super().__init__("Publication resource", path)


class UnresolvablePositionError(DomainError):
    """Raised when the book's EPUB does not hold the place a browser's locator names.

    The writer's own problem rather than the book's: a locator from a different
    edition, or one matched too weakly to store as where the reader is.
    """


class BookFileUnreadableError(DomainError):
    """Raised when a book's stored file cannot be read, so no position can be placed in it.

    Separate from :class:`UnresolvablePositionError` because nothing the browser
    sends would fare any better -- every position in the book fails together.
    """


class PublicationIndexUnavailableError(DomainError):
    """Raised when a book's index cannot be read back after being derived.

    Deriving an index stores it best-effort, so a failed write leaves a book
    that exists but has nothing to serve from -- a server fault, not a 404.
    """

    def __init__(self, book_id: int) -> None:
        super().__init__(f"No publication index could be stored for book {book_id}")
