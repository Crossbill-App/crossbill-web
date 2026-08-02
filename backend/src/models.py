"""ORM model aggregator.

ORM models live per-subdomain under ``src/infrastructure/<subdomain>/orm/``.
This module imports every one of them so that they are registered on
``Base.metadata`` (used by Alembic autogenerate and table creation) and
re-exports them for convenience. Prefer importing models from their owning
subdomain's ``orm`` package directly.
"""

from src.database import Base
from src.infrastructure.ai.orm.ai_usage_record_model import AIUsageRecord
from src.infrastructure.identity.orm.refresh_token_model import RefreshToken
from src.infrastructure.identity.orm.user_model import User
from src.infrastructure.jobs.orm.job_batch_model import JobBatchModel
from src.infrastructure.learning.orm.ai_chat_session_model import AIChatSession
from src.infrastructure.learning.orm.flashcard_model import Flashcard
from src.infrastructure.library.orm.book_model import Book
from src.infrastructure.library.orm.chapter_model import Chapter
from src.infrastructure.notes.orm.associations import (
    note_books,
    note_chapters,
    note_highlights,
    note_tags,
)
from src.infrastructure.notes.orm.note_model import Note
from src.infrastructure.reading.orm.associations import (
    highlight_tags,
    reading_session_highlights,
)
from src.infrastructure.reading.orm.bookmark_model import Bookmark
from src.infrastructure.reading.orm.chapter_digest_model import (
    ChapterDigest,
)
from src.infrastructure.reading.orm.highlight_model import Highlight
from src.infrastructure.reading.orm.highlight_style_model import HighlightStyle
from src.infrastructure.reading.orm.reading_session_model import ReadingSession
from src.infrastructure.reflection.orm.associations import book_reflection_notes
from src.infrastructure.reflection.orm.book_reflection_model import BookReflection
from src.infrastructure.tagging.orm.tag_group_model import TagGroup
from src.infrastructure.tagging.orm.tag_model import Tag

__all__ = [
    "AIChatSession",
    "AIUsageRecord",
    "Base",
    "Book",
    "BookReflection",
    "Bookmark",
    "Chapter",
    "ChapterDigest",
    "Flashcard",
    "Highlight",
    "HighlightStyle",
    "JobBatchModel",
    "Note",
    "ReadingSession",
    "RefreshToken",
    "Tag",
    "TagGroup",
    "User",
    "book_reflection_notes",
    "highlight_tags",
    "note_books",
    "note_chapters",
    "note_highlights",
    "note_tags",
    "reading_session_highlights",
]
