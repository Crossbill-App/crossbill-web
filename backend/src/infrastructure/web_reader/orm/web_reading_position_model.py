"""SQLAlchemy ORM model for a book's last web-reader position."""

from datetime import datetime as dt
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.database import Base


class WebReadingPosition(Base):
    """Where a reader last was in a book they are reading in the browser.

    One row per reader and book. ``reading_session_id`` is ``ON DELETE SET
    NULL``: a deleted session is the same as having no open one, which starts
    the next write a new session rather than taking the position row with it.
    """

    __tablename__ = "web_reading_positions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # The Readium Locator exactly as the navigator produced it. Opaque here on
    # purpose: it is derived, never canonical (ADR-0004 §2), and the only thing
    # that will ever read it back is another navigator.
    locator: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(PG_JSONB, "postgresql"), nullable=False
    )
    xpoint: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    # The digest of the EPUB the locator was derived from, as on `highlights`
    # and `reading_sessions`: a row whose hash no longer matches the stored file
    # describes a book that has been replaced.
    locator_source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reading_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="SET NULL"), nullable=True
    )
    # The server's clock, ordering writes; WebReadingPosition says why the reader's cannot.
    updated_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    # The reader's clock: when they were at the position stored here.
    recorded_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_web_reading_position_user_book"),
    )

    def __repr__(self) -> str:
        """String representation of WebReadingPosition."""
        return f"<WebReadingPosition(id={self.id}, book_id={self.book_id})>"
