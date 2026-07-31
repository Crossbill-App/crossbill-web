"""Add replaced_by_jti to refresh_tokens

Records which token a rotated refresh token was exchanged for, so that
re-presenting the spent token shortly afterwards can return its replacement
instead of being mistaken for a replay.

Revision ID: 060
Revises: 059
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "060"
down_revision: str | Sequence[str] | None = "059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("replaced_by_jti", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "replaced_by_jti")
