"""SQLAlchemy ORM model for highlights."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.database import Base
from src.infrastructure.reading.orm.associations import (
    highlight_tags,
    reading_session_highlights,
)

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.user_model import User
    from src.infrastructure.learning.orm.flashcard_model import Flashcard
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.library.orm.chapter_model import Chapter
    from src.infrastructure.reading.orm.bookmark_model import Bookmark
    from src.infrastructure.reading.orm.highlight_style_model import HighlightStyle
    from src.infrastructure.reading.orm.reading_session_model import ReadingSession
    from src.infrastructure.tagging.orm.tag_model import Tag


class Highlight(Base):
    """Highlight model for storing KOReader highlights."""

    __tablename__ = "highlights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), index=True, nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(nullable=True)
    start_xpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_xpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    highlight_style_id: Mapped[int | None] = mapped_column(
        ForeignKey("highlight_styles.id", ondelete="SET NULL"), index=True, nullable=True
    )
    datetime: Mapped[str] = mapped_column(String(50), nullable=False)  # KOReader datetime string
    koreader_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SHA-256 hash for deduplication
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[dt | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    text_search_vector: Mapped[str | None] = mapped_column(
        Text().with_variant(TSVECTOR, "postgresql"), nullable=True, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="highlights")
    book: Mapped["Book"] = relationship(back_populates="highlights")
    chapter: Mapped["Chapter | None"] = relationship(back_populates="highlights")
    highlight_style_rel: Mapped["HighlightStyle | None"] = relationship(back_populates="highlights")
    tags: Mapped[list["Tag"]] = relationship(
        secondary=highlight_tags, back_populates="highlights", lazy="selectin"
    )
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="highlight", cascade="all, delete-orphan"
    )
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="highlight", cascade="all, delete-orphan"
    )
    reading_sessions: Mapped[list["ReadingSession"]] = relationship(
        secondary=reading_session_highlights, back_populates="highlights", lazy="selectin"
    )

    # Unique constraint for deduplication: same content hash within same book
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", "content_hash", name="uq_highlight_content_hash"),
    )

    def __repr__(self) -> str:
        """String representation of Highlight."""
        return f"<Highlight(id={self.id}, text='{self.text[:50]}...', book_id={self.book_id})>"
