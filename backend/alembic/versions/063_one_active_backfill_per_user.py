"""Allow only one active content-embedding backfill per user

A partial unique index rather than an application-level check: the guard exists
to stop a double-tap on the backfill button, and read-then-insert races exactly
that. Only the backfill type is constrained -- upload-driven CONTENT_EMBEDDING
batches must never be refused.

Revision ID: 063
Revises: 062
"""

from collections.abc import Sequence

from alembic import op

revision: str = "063"
down_revision: str | Sequence[str] | None = "062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_job_batches_active_backfill_per_user"


def upgrade() -> None:
    op.execute(
        f"CREATE UNIQUE INDEX {INDEX_NAME} ON job_batches (user_id) "
        "WHERE batch_type = 'content_embedding_backfill' "
        "AND status IN ('pending', 'running')"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX {INDEX_NAME}")
