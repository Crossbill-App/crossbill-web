"""SQLAlchemy ORM model for Page Views."""

from datetime import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.database import Base


class PageView(Base):
    """One page on screen during a reading session."""

    __tablename__ = "page_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    reading_session_id: Mapped[int] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_xpoint: Mapped[str] = mapped_column(Text, nullable=False)
    end_xpoint: Mapped[str] = mapped_column(Text, nullable=False)
    start_position: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    end_position: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    position_source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    shown_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
