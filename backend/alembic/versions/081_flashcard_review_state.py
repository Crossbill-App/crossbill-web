"""Give flashcards a review status, an origin and FSRS review state, and log their reviews

Every existing card is active and hand-made. The FSRS columns stay null until a
card's first review; flashcard_reviews is the log they are derived from.

Revision ID: 081
Revises: 080
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "081"
down_revision: str | Sequence[str] | None = "080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "flashcards",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.add_column(
        "flashcards",
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
    )
    op.add_column("flashcards", sa.Column("fsrs_state", sa.String(20), nullable=True))
    op.add_column("flashcards", sa.Column("step", sa.Integer(), nullable=True))
    op.add_column("flashcards", sa.Column("stability", sa.Float(), nullable=True))
    op.add_column("flashcards", sa.Column("difficulty", sa.Float(), nullable=True))
    op.add_column("flashcards", sa.Column("due", sa.DateTime(timezone=True), nullable=True))
    op.add_column("flashcards", sa.Column("last_review", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_flashcards_user_id_status_due", "flashcards", ["user_id", "status", "due"])

    op.create_table(
        "flashcard_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "flashcard_id",
            sa.Integer(),
            sa.ForeignKey("flashcards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "flashcard_id",
            "reviewed_at",
            name="uq_flashcard_reviews_flashcard_id_reviewed_at",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("flashcard_reviews")
    op.drop_index("ix_flashcards_user_id_status_due", table_name="flashcards")
    for column in (
        "last_review",
        "due",
        "difficulty",
        "stability",
        "step",
        "fsrs_state",
        "origin",
        "status",
    ):
        op.drop_column("flashcards", column)
