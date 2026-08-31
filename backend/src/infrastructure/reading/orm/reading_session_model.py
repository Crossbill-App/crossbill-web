"""SQLAlchemy ORM model for reading sessions."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.database import Base
from src.infrastructure.reading.orm.associations import reading_session_highlights

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.user_model import User
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.reading.orm.highlight_model import Highlight


class ReadingSession(Base):
    """ReadingSession model for tracking reading sessions from KOReader."""

    __tablename__ = "reading_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_time: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    start_xpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_xpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_page: Mapped[int | None] = mapped_column(nullable=True)
    end_page: Mapped[int | None] = mapped_column(nullable=True)
    start_position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    end_position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SHA-256 hash for deduplication
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="reading_sessions")
    book: Mapped["Book"] = relationship(back_populates="reading_sessions")
    highlights: Mapped[list["Highlight"]] = relationship(
        secondary=reading_session_highlights, back_populates="reading_sessions", lazy="selectin"
    )

    # Unique constraint for deduplication: same content hash for same user
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_reading_session_content_hash"),
    )

    def __repr__(self) -> str:
        """String representation of ReadingSession."""
        return (
            f"<ReadingSession(id={self.id}, book_id={self.book_id}, start_time={self.start_time})>"
        )
