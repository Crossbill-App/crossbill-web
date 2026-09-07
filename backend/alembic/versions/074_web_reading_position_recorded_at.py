"""Separate when a position was written from when the reader was at it

``updated_at`` is the server's clock and answers *which of two writes is later*,
which has to be a fact about this server. It cannot also answer *has the reader
moved*: a second tab idling on page 20 while the first advances to page 100
sends its closing write with a perfectly fresh arrival, and would overwrite page
100 with the page it has been sitting on for an hour.

``recorded_at`` is the reader's own clock -- when they were at the position the
write carries -- and it is the watermark a position must beat to move. A write
that does not beat it still lands: it extends the reading session and may close
it, and simply leaves the newer position where it is.

Backfilled from ``updated_at``, which is what the column meant until now.

Revision ID: 074
Revises: 073
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "074"
down_revision: str | Sequence[str] | None = "073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "web_reading_positions",
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE web_reading_positions SET recorded_at = updated_at")
    op.alter_column("web_reading_positions", "recorded_at", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("web_reading_positions", "recorded_at")
