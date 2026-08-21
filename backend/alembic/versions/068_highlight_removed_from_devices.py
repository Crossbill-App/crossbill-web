"""Withhold a highlight from e-readers without deleting it

A highlight deleted on a device must not come back on the next pull, but the
user's flashcards, bookmarks and notes hang off it, so the server keeps it
(#596). This timestamp marks that second state: the highlight stays whole on
the web and only the ereader pull skips it. Null means it still syncs, which
is every row written before this migration.

Revision ID: 068
Revises: 067
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "068"
down_revision: str | Sequence[str] | None = "067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "highlights",
        sa.Column("removed_from_devices_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_highlights_removed_from_devices_at"),
        "highlights",
        ["removed_from_devices_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_highlights_removed_from_devices_at"), table_name="highlights")
    op.drop_column("highlights", "removed_from_devices_at")
