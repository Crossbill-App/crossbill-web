"""SQLAlchemy ORM model for content embeddings."""

from datetime import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.database import Base

# The embedding dimension is fixed to bge-m3 (1024) and mirrors
# EMBEDDING_DIMENSIONS; a dimension change is a new migration by design.
EMBEDDING_DIMENSIONS = 1024


class Embedding(Base):
    """A dense vector for one content unit, keyed polymorphically by type + id.

    The ``vector`` column only exists on Postgres (pgvector); the test suite runs
    on SQLite, which has no such type, so it degrades to JSON there — the same
    dialect-conditional pattern the highlight ``TSVECTOR`` column uses.
    """

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_id: Mapped[int] = mapped_column(Integer, nullable=False)
    book_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(
        JSON().with_variant(Vector(EMBEDDING_DIMENSIONS), "postgresql"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("content_type", "content_id", name="uq_embeddings_content"),)

    def __repr__(self) -> str:
        """String representation of Embedding."""
        return (
            f"<Embedding(content_type={self.content_type}, "
            f"content_id={self.content_id}, model={self.model_name}@{self.model_version})>"
        )
