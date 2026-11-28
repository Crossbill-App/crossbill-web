"""Who wrote a flashcard."""

from enum import StrEnum


class FlashcardOrigin(StrEnum):
    """A card the reader wrote, or one generated for them."""

    MANUAL = "manual"
    GENERATED = "generated"
