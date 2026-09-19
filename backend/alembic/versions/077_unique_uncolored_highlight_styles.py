"""Make a book's style row with neither device color nor style unique

041 gave every level of the label hierarchy a partial unique index but one: a
book-level row whose ``device_color`` and ``device_style`` are both NULL, which
is what a KOReader highlight synced without color or drawer gets. Two uploads
racing for such a book could each insert one, after which every later
``find_or_create`` for it raised ``MultipleResultsFound`` (#870).

Duplicates are merged first: highlights move to the survivor -- a row carrying a
label or UI color if there is one, else the oldest -- and the rest are deleted.

Revision ID: 077
Revises: 076
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "077"
down_revision: str | Sequence[str] | None = "076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UNCOLORED = "book_id IS NOT NULL AND device_color IS NULL AND device_style IS NULL"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TEMPORARY TABLE hs_survivors AS
        SELECT id AS duplicate_id,
               FIRST_VALUE(id) OVER (
                   PARTITION BY user_id, book_id
                   ORDER BY (label IS NULL AND ui_color IS NULL), id
               ) AS survivor_id
        FROM highlight_styles
        WHERE book_id IS NOT NULL AND device_color IS NULL AND device_style IS NULL
        """
    )
    op.execute(
        """
        UPDATE highlights
        SET highlight_style_id = (
            SELECT survivor_id FROM hs_survivors WHERE duplicate_id = highlight_style_id
        )
        WHERE highlight_style_id IN (
            SELECT duplicate_id FROM hs_survivors WHERE duplicate_id <> survivor_id
        )
        """
    )
    op.execute(
        """
        DELETE FROM highlight_styles
        WHERE id IN (SELECT duplicate_id FROM hs_survivors WHERE duplicate_id <> survivor_id)
        """
    )
    op.execute("DROP TABLE hs_survivors")

    op.create_index(
        "uq_hs_book_none",
        "highlight_styles",
        ["user_id", "book_id"],
        unique=True,
        postgresql_where=sa.text(_UNCOLORED),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_hs_book_none", table_name="highlight_styles")
