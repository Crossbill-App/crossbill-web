"""SQLAlchemy ORM model for highlight styles."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.user_model import User
    from src.infrastructure.library.orm.book_model import Book
    from src.infrastructure.reading.orm.highlight_model import Highlight


def _unique_per_level(name: str, book: bool, color: bool, style: bool) -> Index:
    """A unique index over one level of the label hierarchy.

    Partial because a plain unique constraint treats NULLs as distinct, which
    would let every level with a NULL dimension hold duplicates.
    """
    levels = {"book_id": book, "device_color": color, "device_style": style}
    where = text(" AND ".join(f"{col} IS {'NOT ' if on else ''}NULL" for col, on in levels.items()))
    columns = ["user_id", *(col for col, on in levels.items() if on)]
    return Index(name, *columns, unique=True, postgresql_where=where, sqlite_where=where)


class HighlightStyle(Base):
    """HighlightStyle model for storing highlight style labels and colors."""

    __tablename__ = "highlight_styles"
    __table_args__ = (
        _unique_per_level("uq_hs_all", book=True, color=True, style=True),
        _unique_per_level("uq_hs_book_color", book=True, color=True, style=False),
        _unique_per_level("uq_hs_book_style", book=True, color=False, style=True),
        _unique_per_level("uq_hs_book_none", book=True, color=False, style=False),
        _unique_per_level("uq_hs_global_combo", book=False, color=True, style=True),
        _unique_per_level("uq_hs_global_color", book=False, color=True, style=False),
        _unique_per_level("uq_hs_global_style", book=False, color=False, style=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), index=True, nullable=True
    )
    device_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ui_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
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
    user: Mapped["User"] = relationship(back_populates="highlight_styles")
    book: Mapped["Book | None"] = relationship(back_populates="highlight_styles")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="highlight_style_rel")

    def __repr__(self) -> str:
        """String representation of HighlightStyle."""
        return (
            f"<HighlightStyle(id={self.id}, user_id={self.user_id}, "
            f"device_color='{self.device_color}', device_style='{self.device_style}')>"
        )
