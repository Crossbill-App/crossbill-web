"""SQLAlchemy ORM model for flashcards."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.user_model import User
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.library.orm.chapter_model import Chapter
    from src.infrastructure.reading.orm.highlight_model import Highlight


class Flashcard(Base):
    """Flashcard model for creating study cards from highlights."""

    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
    )
    highlight_id: Mapped[int | None] = mapped_column(
        ForeignKey("highlights.id", ondelete="CASCADE"), index=True, nullable=True
    )
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # SET NULL: notes are hard-deleted; the flashcard survives as a book-level card
    note_id: Mapped[int | None] = mapped_column(
        ForeignKey("notes.id", ondelete="SET NULL"), index=True, nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    origin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    fsrs_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    due: Mapped[dt | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_review: Mapped[dt | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    user: Mapped["User"] = relationship(back_populates="flashcards")
    book: Mapped["Book"] = relationship(back_populates="flashcards")
    highlight: Mapped["Highlight | None"] = relationship(back_populates="flashcards")
    chapter: Mapped["Chapter | None"] = relationship()

    __table_args__ = (Index("ix_flashcards_user_id_status_due", "user_id", "status", "due"),)

    def __repr__(self) -> str:
        """String representation of Flashcard."""
        return (
            f"<Flashcard(id={self.id}, book_id={self.book_id}, highlight_id={self.highlight_id})>"
        )
