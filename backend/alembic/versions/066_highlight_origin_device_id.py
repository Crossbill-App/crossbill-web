"""Record which device a highlight was uploaded from

An upload batch comes from one device, so the id is stamped on every highlight
it creates. Pulling highlights back (#590) needs it: the device that made a
highlight should be able to tell its own from the ones it is receiving.

Revision ID: 066
Revises: 065
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "066"
down_revision: str | Sequence[str] | None = "065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("highlights", sa.Column("origin_device_id", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("highlights", "origin_device_id")
