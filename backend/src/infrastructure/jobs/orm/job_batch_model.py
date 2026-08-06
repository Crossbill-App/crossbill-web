"""SQLAlchemy ORM model for job batches."""

from datetime import datetime as dt

from sqlalchemy import DateTime, Index, Integer, String, and_, column, func
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import JSON

from src.database import Base
from src.domain.jobs.entities.job_batch import (
    ACTIVE_JOB_BATCH_STATUSES,
    JobBatchType,
)

ONE_ACTIVE_BACKFILL_INDEX = "uq_job_batches_active_backfill_per_user"


def _active_backfill_predicate() -> ColumnElement[bool]:
    """Rows the one-backfill-per-user index covers.

    Built from the enums rather than string literals so a renamed status or type
    breaks here instead of silently emptying the predicate. The migration
    repeats the literals by design -- it is a frozen snapshot.
    """
    return and_(
        column("batch_type") == JobBatchType.CONTENT_EMBEDDING_BACKFILL.value,
        column("status").in_(sorted(s.value for s in ACTIVE_JOB_BATCH_STATUSES)),
    )


class JobBatchModel(Base):
    __tablename__ = "job_batches"

    __table_args__ = (
        Index(
            ONE_ACTIVE_BACKFILL_INDEX,
            "user_id",
            unique=True,
            postgresql_where=_active_backfill_predicate(),
            sqlite_where=_active_backfill_predicate(),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    batch_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    total_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    job_keys: Mapped[list[str]] = mapped_column(
        JSON().with_variant(PG_JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<JobBatchModel(id={self.id}, type={self.batch_type}, status={self.status})>"
