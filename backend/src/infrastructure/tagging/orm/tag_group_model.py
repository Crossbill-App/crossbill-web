"""SQLAlchemy ORM model for tag groups."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.tagging.orm.tag_model import Tag


class TagGroup(Base):
    """TagGroup model for grouping tags within a book."""

    __tablename__ = "tag_groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=False
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
    book: Mapped["Book"] = relationship(back_populates="tag_groups")
    tags: Mapped[list["Tag"]] = relationship(back_populates="tag_group")

    # Unique constraint: tag group names are unique within a book
    __table_args__ = (UniqueConstraint("book_id", "name", name="uq_tag_group_book_name"),)

    def __repr__(self) -> str:
        """String representation of TagGroup."""
        return f"<TagGroup(id={self.id}, name='{self.name}', book_id={self.book_id})>"
