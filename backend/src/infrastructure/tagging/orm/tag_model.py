"""SQLAlchemy ORM model for tags."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

# The highlight association is owned by the reading module, which defines the
# link table; tags only mirror the relationship back.
from src.infrastructure.reading.orm.associations import highlight_tags

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.user_model import User
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.reading.orm.highlight_model import Highlight
    from src.infrastructure.tagging.orm.tag_group_model import TagGroup


class Tag(Base):
    """Tag model for categorizing content within a book (highlights, notes)."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tag_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("tag_groups.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
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
    user: Mapped["User"] = relationship(back_populates="tags")
    book: Mapped["Book"] = relationship(back_populates="tags")
    tag_group: Mapped["TagGroup | None"] = relationship(back_populates="tags", lazy="selectin")
    highlights: Mapped[list["Highlight"]] = relationship(
        secondary=highlight_tags, back_populates="tags", lazy="selectin"
    )

    # Unique constraint: tag names are unique within a book per user
    __table_args__ = (UniqueConstraint("user_id", "book_id", "name", name="uq_tag_user_book_name"),)

    def __repr__(self) -> str:
        """String representation of Tag."""
        return f"<Tag(id={self.id}, name='{self.name}', book_id={self.book_id})>"
