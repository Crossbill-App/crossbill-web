"""Add character offsets for chapters and character totals for books

Chapter Coverage is measured in characters, so a chapter records where its
text starts and a book how many characters it holds. Both stay empty for
existing books until a sync or a web reader position fills them.

Revision ID: 079
Revises: 078
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "079"
down_revision: str | Sequence[str] | None = "078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("chapters", sa.Column("start_offset", sa.Integer(), nullable=True))
    op.add_column("books", sa.Column("total_characters", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("books", "total_characters")
    op.drop_column("chapters", "start_offset")
