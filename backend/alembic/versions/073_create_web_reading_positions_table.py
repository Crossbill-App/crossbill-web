"""Create web_reading_positions: where the browser left off, and the session it is in

One row per reader and book. Reading *progress* is unaffected -- it is still the
latest reading session's ``end_position``, which is why nothing outside the web
reader changes here (ADR-0004, Amendment 3). This table holds the two things a
reading session cannot: the Readium locator, so a browser can be put back
exactly where it was, and the id of the session still being extended.

``reading_session_id`` is SET NULL rather than CASCADE: a deleted session means
there is no open one, which is a fresh session on the next write -- not the loss
of the reader's place.

Revision ID: 073
Revises: 072
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "073"
down_revision: str | Sequence[str] | None = "072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "web_reading_positions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("locator", sa.JSON(), nullable=False),
        sa.Column("xpoint", sa.Text(), nullable=False),
        sa.Column("position", sa.JSON(), nullable=True),
        sa.Column(
            "reading_session_id",
            sa.Integer(),
            sa.ForeignKey("reading_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "book_id", name="uq_web_reading_position_user_book"),
    )
    op.create_index("ix_web_reading_positions_user_id", "web_reading_positions", ["user_id"])
    op.create_index("ix_web_reading_positions_book_id", "web_reading_positions", ["book_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_web_reading_positions_book_id", table_name="web_reading_positions")
    op.drop_index("ix_web_reading_positions_user_id", table_name="web_reading_positions")
    op.drop_table("web_reading_positions")
