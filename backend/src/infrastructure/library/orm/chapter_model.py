"""SQLAlchemy ORM model for chapters."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.reading.orm.chapter_digest_model import (
        ChapterDigest,
    )
    from src.infrastructure.reading.orm.highlight_model import Highlight


class Chapter(Base):
    """Chapter model for storing unique chapters within a book."""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    chapter_number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    start_xpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_xpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    end_position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
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
    book: Mapped["Book"] = relationship(back_populates="chapters")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="chapter")
    digest: Mapped["ChapterDigest | None"] = relationship(
        back_populates="chapter", uselist=False, cascade="all, delete-orphan"
    )
    # Self-referential relationship for hierarchical chapters
    parent: Mapped["Chapter | None"] = relationship(
        "Chapter", remote_side="Chapter.id", back_populates="children"
    )
    children: Mapped[list["Chapter"]] = relationship(
        "Chapter", back_populates="parent", cascade="all, delete-orphan"
    )

    # Unique constraint: chapter names must be unique within same parent level
    # (allows "Harjoitukset" under Part I and "Harjoitukset" under Part II)
    __table_args__ = (UniqueConstraint("book_id", "parent_id", "name", name="uq_chapter_per_book"),)

    def __repr__(self) -> str:
        """String representation of Chapter."""
        return f"<Chapter(id={self.id}, name='{self.name}', book_id={self.book_id})>"
