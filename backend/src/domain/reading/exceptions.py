"""Reading module domain exceptions."""

from src.domain.common.exceptions import (
    BusinessRuleViolationError,
    ConflictError,
    EntityNotFoundError,
)


class BookNotFoundError(EntityNotFoundError):
    """Raised when a book cannot be found."""

    def __init__(self, book_id: int | str) -> None:
        super().__init__("Book", book_id)


class ReadingSessionNotFoundError(EntityNotFoundError):
    """Raised when a reading session cannot be found."""

    def __init__(self, session_id: int) -> None:
        super().__init__("ReadingSession", session_id)


class HighlightNotFoundError(EntityNotFoundError):
    """Raised when a highlight cannot be found."""

    def __init__(self, highlight_id: int) -> None:
        super().__init__("Highlight", highlight_id)


class HighlightAlreadyDeletedError(BusinessRuleViolationError):
    """Raised when trying to delete an already-deleted highlight."""

    def __init__(self, highlight_id: int) -> None:
        super().__init__(
            rule="highlight_not_deleted",
            message=f"Highlight {highlight_id} is already deleted",
        )


class ChapterNotFoundError(EntityNotFoundError):
    """Raised when a chapter cannot be found."""

    def __init__(self, chapter_id: int) -> None:
        super().__init__("Chapter", chapter_id)


class ChapterDigestNotFoundError(EntityNotFoundError):
    """Raised when a chapter's digest cannot be found."""

    def __init__(self, chapter_id: int) -> None:
        super().__init__("ChapterDigest", chapter_id)


class HighlightStyleNotFoundError(EntityNotFoundError):
    """Raised when a highlight style cannot be found."""

    def __init__(self, style_id: int) -> None:
        super().__init__("HighlightStyle", style_id)


class DuplicateHighlightError(ConflictError):
    """Raised when attempting to create a duplicate highlight."""

    def __init__(self, content_hash: str) -> None:
        super().__init__(
            f"Duplicate highlight with hash {content_hash}",
            {"content_hash": content_hash},
        )
