"""Drop the single-column index on books.client_book_id

Every lookup by client_book_id also filters on user_id, which the unique
``uq_book_client_book_id`` index on (user_id, client_book_id) from 026 serves.

Revision ID: 078
Revises: 077
"""

from collections.abc import Sequence

from alembic import op

revision: str = "078"
down_revision: str | Sequence[str] | None = "077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_books_client_book_id", table_name="books")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index("ix_books_client_book_id", "books", ["client_book_id"])
