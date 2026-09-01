"""SQLAlchemy ORM model for notes."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.infrastructure.notes.orm.associations import (
    note_books,
    note_chapters,
    note_highlights,
    note_tags,
)

if TYPE_CHECKING:
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.library.orm.chapter_model import Chapter
    from src.infrastructure.reading.orm.highlight_model import Highlight
    from src.infrastructure.tagging.orm.tag_model import Tag


class Note(Base):
    """User-authored note about terms, characters, or concepts in books."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_notes_user_id_created_at",
            "user_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
    )

    # Relationships (one-directional; notes are always queried from the note side)
    books: Mapped[list["Book"]] = relationship(secondary=note_books, lazy="selectin")
    chapters: Mapped[list["Chapter"]] = relationship(secondary=note_chapters, lazy="selectin")
    highlights: Mapped[list["Highlight"]] = relationship(secondary=note_highlights, lazy="selectin")
    tags: Mapped[list["Tag"]] = relationship(secondary=note_tags, lazy="selectin")

    def __repr__(self) -> str:
        """String representation of Note."""
        return f"<Note(id={self.id}, title='{self.title}', kind={self.kind})>"
