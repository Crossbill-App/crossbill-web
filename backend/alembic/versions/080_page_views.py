"""Add page_views, the pages a reader had on screen in each reading session

One row per Page View, deleted with its session. Positions and character
offsets are derived at ingest from the EPUB that position_source_hash names.

Revision ID: 080
Revises: 079
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "080"
down_revision: str | Sequence[str] | None = "079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "page_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reading_session_id",
            sa.Integer(),
            sa.ForeignKey("reading_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_xpoint", sa.Text(), nullable=False),
        sa.Column("end_xpoint", sa.Text(), nullable=False),
        sa.Column("start_position", sa.JSON(), nullable=False),
        sa.Column("end_position", sa.JSON(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("position_source_hash", sa.String(64), nullable=False),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_page_views_reading_session_id", "page_views", ["reading_session_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_page_views_reading_session_id", table_name="page_views")
    op.drop_table("page_views")
