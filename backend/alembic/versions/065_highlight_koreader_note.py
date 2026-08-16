"""Store the note written on the e-reader alongside a highlight

The KOReader plugin has always sent `note`; the upload dropped it. It is kept
now so that a highlight can be pulled back to a device intact (#590). The web
UI does not read it -- Crossbill notes are the Notes module, this is device
data only.

Revision ID: 065
Revises: 064
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "065"
down_revision: str | Sequence[str] | None = "064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("highlights", sa.Column("koreader_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("highlights", "koreader_note")
