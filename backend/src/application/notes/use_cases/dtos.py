"""DTOs for note use cases."""

from dataclasses import dataclass, field

from src.domain.learning.entities.flashcard import Flashcard
from src.domain.library.entities.chapter import Chapter
from src.domain.notes.entities.note import Note
from src.domain.reading.entities.highlight import Highlight
from src.domain.tagging.entities.tag import Tag


@dataclass
class NoteWithLinkedEntities:
    """A note together with the linked entities needed for display."""

    note: Note
    chapters: list[Chapter]
    highlights: list[Highlight]
    tags: list[Tag]
    # Only populated by the single-note detail use case; list responses
    # intentionally leave this empty.
    flashcards: list[Flashcard] = field(default_factory=list)
