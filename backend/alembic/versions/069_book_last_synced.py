"""Record when a device last sent a book's data

The landing page wants the books a reader is actually reading on their
e-reader, which no existing column answers: ``last_viewed`` is a web click and
``updated_at`` moves on any edit. This stamp moves only when a sync succeeds in
pushing highlights or reading sessions (#643).

Existing books are backfilled from the rows past syncs left behind. Both source
tables carry a server-side ``created_at``, which is the insert time of the sync
that carried them — the same clock the column will use from now on. A book that
has never received either stays null and stays out of the list.

Revision ID: 069
Revises: 068
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "069"
down_revision: str | Sequence[str] | None = "068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BACKFILL = """
UPDATE books
SET last_synced = synced.last_synced
FROM (
    SELECT book_id, MAX(created_at) AS last_synced
    FROM (
        SELECT book_id, created_at FROM highlights
        UNION ALL
        SELECT book_id, created_at FROM reading_sessions
    ) AS synced_rows
    GROUP BY book_id
) AS synced
WHERE books.id = synced.book_id
"""


def upgrade() -> None:
    op.add_column("books", sa.Column("last_synced", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        op.f("ix_books_last_synced"),
        "books",
        ["last_synced"],
        unique=False,
    )
    op.execute(sa.text(BACKFILL))


def downgrade() -> None:
    op.drop_index(op.f("ix_books_last_synced"), table_name="books")
    op.drop_column("books", "last_synced")
