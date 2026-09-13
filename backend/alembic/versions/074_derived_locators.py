"""Hold the Readium Locator derived from each stored xpointer

A locator is derived from the book's EPUB when a position arrives and read back
without one (ADR-0004, Amendment 6); ``locator_source_hash`` names the EPUB it
came from, so a row can be told it is stale rather than silently describing a
file that has since been replaced. A null locator beside a hash therefore says
that file could not place the position; a null with no hash says none was tried.

``highlights.locator_confidence`` is landed here with no writer: the forward
conversion returns a locator ungraded, and a grade comes back only from the
reverse direction M4 (#749) adds. ``reading_sessions`` gets no such column at
all, because a reading position has no quote to verify against (Amendment 3).

Revision ID: 074
Revises: 073
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "074"
down_revision: str | Sequence[str] | None = "073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOCATOR_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("highlights", sa.Column("locator", _LOCATOR_JSON, nullable=True))
    op.add_column("highlights", sa.Column("locator_confidence", sa.SmallInteger(), nullable=True))
    op.add_column("highlights", sa.Column("locator_source_hash", sa.String(64), nullable=True))
    op.add_column("reading_sessions", sa.Column("start_locator", _LOCATOR_JSON, nullable=True))
    op.add_column("reading_sessions", sa.Column("end_locator", _LOCATOR_JSON, nullable=True))
    op.add_column(
        "reading_sessions", sa.Column("locator_source_hash", sa.String(64), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("reading_sessions", "locator_source_hash")
    op.drop_column("reading_sessions", "end_locator")
    op.drop_column("reading_sessions", "start_locator")
    op.drop_column("highlights", "locator_source_hash")
    op.drop_column("highlights", "locator_confidence")
    op.drop_column("highlights", "locator")
