"""SQLAlchemy ORM model for refresh tokens."""

from datetime import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.infrastructure.identity.orm.user_model import User


class RefreshToken(Base):
    """Refresh token for token rotation and replay detection."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revoked_at: Mapped[dt | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The token this one was rotated into. Set only by rotation, so a token
    # revoked outright (logout, password change) can never be traded back in.
    replaced_by_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[dt] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, jti='{self.jti}', user_id={self.user_id})>"
