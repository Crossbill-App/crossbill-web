"""SQLAlchemy ORM model for a book's last web-reader position."""

from datetime import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.database import Base


class WebReadingPosition(Base):
    """Where a reader last was in a book they are reading in the browser.

    One row per reader and book. Reading *progress* is not read from here -- it
    is still the latest reading session's ``end_position``, which is why nothing
    outside the web reader had to learn about this table (ADR-0004, Amendment
    3). What lives here is the locator, so a browser can be put back where it
    was, and the id of the reading session still being extended.

    ``reading_session_id`` is ``ON DELETE SET NULL``: deleting a session is the
    same as having no open one, which starts the next write a new session rather
    than taking the position row with it.
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
    locator: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    xpoint: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    reading_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="SET NULL"), nullable=True
    )
    # The server's clock: which of two writes is later. A fact about this server,
    # so that a device with a slow clock is not locked out of writing for good.
    updated_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    # The reader's clock: when they were at the position stored here. The
    # watermark a write must beat to *move* the position -- distinct from
    # `updated_at`, because an idle tab's closing write arrives perfectly fresh
    # and is still carrying a page the reader left an hour ago.
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
