"""DTOs for flashcard use cases."""

from dataclasses import dataclass

from src.domain.learning.entities.flashcard import Flashcard
from src.domain.library.entities.chapter import Chapter
from src.domain.reading.entities.highlight import Highlight
from src.domain.tagging.entities.tag import Tag


@dataclass
class FlashcardWithHighlight:
    """DTO for flashcard with its associated highlight and tags."""

    flashcard: Flashcard
    highlight: Highlight | None
    chapter: Chapter | None
    tags: list[Tag]
