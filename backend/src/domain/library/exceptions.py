"""Library domain exceptions."""

from src.domain.common.exceptions import EntityNotFoundError, ValidationError


class CoverNotFoundError(EntityNotFoundError):
    """Raised when a book cover image cannot be found."""

    def __init__(self, filename: str) -> None:
        super().__init__("Cover", filename)


class EbookFileNotFoundError(EntityNotFoundError):
    """Raised when a book has no stored ebook file to read from.

    Distinct from ``BookNotFoundError``: the book is there and the user owns it,
    but nothing was ever uploaded for it or the stored file has since gone
    missing. Both answer 404, and keeping them apart is what stops a storage
    fault from reading as a deleted book in the logs.
    """

    def __init__(self, book_id: int) -> None:
        super().__init__("Ebook file for book", book_id)
        self.book_id = book_id


class XPointNavigationError(ValidationError):
    """Could not navigate to xpoint location in EPUB."""

    def __init__(self, xpoint: str, reason: str) -> None:
        super().__init__(
            f"Cannot navigate to xpoint '{xpoint}': {reason}",
            field="xpoint",
            value=xpoint,
        )
        self.xpoint = xpoint
        self.reason = reason


class InvalidEbookError(ValidationError):
    """Invalid ebook file."""

    def __init__(self, reason: str, ebook_type: str = "ebook") -> None:
        super().__init__(
            f"Invalid {ebook_type}: {reason}",
            field="ebook",
        )
        self.reason = reason
        self.ebook_type = ebook_type
