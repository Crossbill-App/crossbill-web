"""Store when a highlight was last edited on the e-reader

Two devices can edit the same highlight's note or colour, and the server has to
decide which edit survives (#590). KOReader's own rule is the newest edit wins,
so the device's `datetime_updated` travels with every upload and is kept here.
Rows written before this migration have none; their creation `datetime` stands
in, which is older than any real edit.

Revision ID: 067
Revises: 066
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "067"
down_revision: str | Sequence[str] | None = "066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "highlights", sa.Column("koreader_updated_at", sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("highlights", "koreader_updated_at")
