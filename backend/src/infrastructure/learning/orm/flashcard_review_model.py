"""SQLAlchemy ORM model for Flashcard Reviews."""

from datetime import datetime as dt

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class FlashcardReview(Base):
    """One rating of a flashcard; the log its review state is derived from."""

    __tablename__ = "flashcard_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    flashcard_id: Mapped[int] = mapped_column(
        ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(String(10), nullable=False)
    reviewed_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "flashcard_id", "reviewed_at", name="uq_flashcard_reviews_flashcard_id_reviewed_at"
        ),
    )
