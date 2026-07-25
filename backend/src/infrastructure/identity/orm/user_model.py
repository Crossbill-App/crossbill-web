"""SQLAlchemy ORM model for users."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.refresh_token_model import RefreshToken
    from src.infrastructure.learning.orm.flashcard_model import Flashcard
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.reading.orm.highlight_model import Highlight
    from src.infrastructure.reading.orm.highlight_style_model import HighlightStyle
    from src.infrastructure.reading.orm.reading_session_model import ReadingSession
    from src.infrastructure.tagging.orm.tag_model import Tag


class User(Base):
    """User model for multi-user support."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    books: Mapped[list["Book"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    highlights: Mapped[list["Highlight"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    highlight_styles: Mapped[list["HighlightStyle"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reading_sessions: Mapped[list["ReadingSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, email='{self.email}')>"
