"""Web reader domain exceptions."""

from src.domain.common.exceptions import DomainError, EntityNotFoundError


class UnresolvablePositionError(DomainError):
    """A locator from the browser does not identify one place in this book.

    The canonical position is the KOReader xpointer, so a position made in the
    browser has to be converted before it can be stored (ADR-0004 §2), and that
    conversion is a text search that grades itself (§5). This is what a grade
    below the floor -- or a search that found nothing at all -- comes back as.

    Deliberately *not* a ``ValidationError``: the request is well-formed and the
    caller could not have sent anything better. What failed is placing the quote
    in the book, which is why it answers 422 rather than the 400 an unreadable
    EPUB gets.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Cannot place this position in the book: {reason}")
        self.reason = reason


class PublicationResourceNotFoundError(EntityNotFoundError):
    """Raised when a publication does not contain the requested file.

    Distinct from ``BookNotFoundError`` and ``EbookFileNotFoundError``: the book
    is there, its EPUB is readable, and the path simply names nothing the
    publication offers -- a stale href, a typo, or somebody probing for the
    package document. All three answer 404, and keeping them apart is what lets
    the logs tell a broken reader from a missing file.
    """

    def __init__(self, path: str) -> None:
        super().__init__("Publication resource", path)
        self.path = path
