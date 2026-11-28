"""Whether a flashcard takes part in review."""

from enum import StrEnum


class FlashcardStatus(StrEnum):
    """A suspended card is never due and takes no reviews until it is unsuspended."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
