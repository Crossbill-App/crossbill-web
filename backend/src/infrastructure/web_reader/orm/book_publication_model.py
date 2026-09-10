"""SQLAlchemy ORM model for a book's stored publication index."""

from datetime import datetime as dt
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.database import Base


class BookPublication(Base):
    """ORM model for the publication index derived from a book's EPUB."""

    __tablename__ = "book_publications"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    # The digest of the EPUB the row was derived from: a row whose hash no longer
    # matches the stored file is stale, whatever the JSON says.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    publication: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(PG_JSONB, "postgresql"), nullable=False
    )
    derived_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        """String representation of BookPublication."""
        return f"<BookPublication(book_id={self.book_id})>"
