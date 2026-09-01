"""Index the newest-first reads behind the landing page's capture feed

The feed asks each table for a reader's newest rows on every landing-page
load. Without these, both sides scan every row the reader owns and sort it.

Revision ID: 072
Revises: 071
"""

from collections.abc import Sequence

from alembic import op

revision: str = "072"
down_revision: str | Sequence[str] | None = "071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_highlights_user_id_datetime",
        "highlights",
        ["user_id", "datetime"],
        postgresql_ops={"datetime": "DESC"},
    )
    op.create_index(
        "ix_notes_user_id_created_at",
        "notes",
        ["user_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_notes_user_id_created_at", table_name="notes")
    op.drop_index("ix_highlights_user_id_datetime", table_name="highlights")
