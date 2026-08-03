"""SQLAlchemy ORM model for content embeddings."""

from datetime import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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
    # Cascade anchors. content_type + content_id remains the logical key, but a
    # polymorphic id cannot carry a constraint, so nothing would prune a row
    # whose note or digest was deleted. Exactly one of these is set and always
    # equals content_id (see the CHECK below), letting the database do it.
    note_id: Mapped[int | None] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), index=True, nullable=True
    )
    highlight_id: Mapped[int | None] = mapped_column(
        ForeignKey("highlights.id", ondelete="CASCADE"), index=True, nullable=True
    )
    digest_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapter_digests.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # SET NULL, not CASCADE: book_id is a scoping hint, not identity. A note can
    # outlive the book it was linked to, so deleting that book must clear the
    # scope rather than drop a live note's embedding. Content that genuinely
    # dies with the book is cascaded by the typed FKs above.
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), index=True, nullable=True
    )
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

    __table_args__ = (
        UniqueConstraint("content_type", "content_id", name="uq_embeddings_content"),
        CheckConstraint(
            "(content_type = 'note' AND note_id = content_id "
            "AND highlight_id IS NULL AND digest_id IS NULL) OR "
            "(content_type = 'highlight' AND highlight_id = content_id "
            "AND note_id IS NULL AND digest_id IS NULL) OR "
            "(content_type = 'digest' AND digest_id = content_id "
            "AND note_id IS NULL AND highlight_id IS NULL)",
            name="ck_embeddings_one_typed_id",
        ),
    )

    def __repr__(self) -> str:
        """String representation of Embedding."""
        return (
            f"<Embedding(content_type={self.content_type}, "
            f"content_id={self.content_id}, model={self.model_name}@{self.model_version})>"
        )
