"""SQLAlchemy ORM model for chapter digests."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.library.orm.chapter_model import Chapter


class ChapterDigest(Base):
    """ORM model for a chapter digest."""

    __tablename__ = "chapter_digests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    keypoints: Mapped[list[str]] = mapped_column(
        JSON().with_variant(PG_JSONB, "postgresql"), nullable=False
    )
    questions: Mapped[list[dict[str, str]]] = mapped_column(
        JSON().with_variant(PG_JSONB, "postgresql"), nullable=False, server_default="[]"
    )
    generated_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    chapter: Mapped["Chapter"] = relationship(back_populates="digest")

    def __repr__(self) -> str:
        """String representation of ChapterDigest."""
        return f"<ChapterDigest(id={self.id}, chapter_id={self.chapter_id})>"
