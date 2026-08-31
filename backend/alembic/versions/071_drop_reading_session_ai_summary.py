"""Drop the reading session AI summary column

The session page no longer generates or renders AI summaries, so nothing reads
or writes ``reading_sessions.ai_summary`` any more. The column goes with the
feature; the session rows themselves are untouched.

The stored summaries are dropped with it. They were derived from the book's own
text, so nothing original is lost, and ``downgrade`` can only bring the column
back empty.

Revision ID: 071
Revises: 070
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "071"
down_revision: str | Sequence[str] | None = "070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("reading_sessions", "ai_summary")


def downgrade() -> None:
    op.add_column("reading_sessions", sa.Column("ai_summary", sa.Text(), nullable=True))
