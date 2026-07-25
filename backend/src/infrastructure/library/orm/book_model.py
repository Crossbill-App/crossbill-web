"""SQLAlchemy ORM model for books."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.user_model import User
    from src.infrastructure.learning.orm.flashcard_model import Flashcard
    from src.infrastructure.library.orm.chapter_model import Chapter
    from src.infrastructure.reading.orm.bookmark_model import Bookmark
    from src.infrastructure.reading.orm.highlight_model import Highlight
    from src.infrastructure.reading.orm.highlight_style_model import HighlightStyle
    from src.infrastructure.reading.orm.reading_session_model import ReadingSession
    from src.infrastructure.tagging.orm.tag_group_model import TagGroup
    from src.infrastructure.tagging.orm.tag_model import Tag


class Book(Base):
    """Book model for storing book metadata."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ebook_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cover_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_blurhash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    client_book_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )  # Client-provided stable book identifier
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_viewed: Mapped[dt | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    end_position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    reading_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="books")
    highlights: Mapped[list["Highlight"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    highlight_styles: Mapped[list["HighlightStyle"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    tag_groups: Mapped[list["TagGroup"]] = relationship(
        back_populates="book", cascade="all, delete-orphan", lazy="selectin"
    )
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    reading_sessions: Mapped[list["ReadingSession"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of Book."""
        return f"<Book(id={self.id}, title='{self.title}')>"
