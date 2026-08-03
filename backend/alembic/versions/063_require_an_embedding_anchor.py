"""Make the embedding anchor CHECK reject a row with no anchor at all.

Revision ID: 063
Revises: 062
"""

from collections.abc import Sequence

from alembic import op

revision: str = "063"
down_revision: str | Sequence[str] | None = "062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_embeddings_one_typed_id"

# 062's form compared each anchor to content_id without first requiring it to be
# set. With every anchor NULL the comparison yields NULL, the whole disjunction
# yields NULL, and SQL takes a CHECK that is not false as satisfied -- so the
# constraint accepted exactly the row it exists to forbid: one no foreign key
# can cascade. The IS NOT NULL tests force false instead of NULL.
_ANCHORED = (
    "(content_type = 'note' AND note_id IS NOT NULL AND note_id = content_id "
    "AND highlight_id IS NULL AND digest_id IS NULL) OR "
    "(content_type = 'highlight' AND highlight_id IS NOT NULL AND highlight_id = content_id "
    "AND note_id IS NULL AND digest_id IS NULL) OR "
    "(content_type = 'digest' AND digest_id IS NOT NULL AND digest_id = content_id "
    "AND note_id IS NULL AND highlight_id IS NULL)"
)

_ORIGINAL = (
    "(content_type = 'note' AND note_id = content_id "
    "AND highlight_id IS NULL AND digest_id IS NULL) OR "
    "(content_type = 'highlight' AND highlight_id = content_id "
    "AND note_id IS NULL AND digest_id IS NULL) OR "
    "(content_type = 'digest' AND digest_id = content_id "
    "AND note_id IS NULL AND highlight_id IS NULL)"
)


def upgrade() -> None:
    """Upgrade schema."""
    # Any anchorless row predates the constraint being able to reject it, and it
    # is unreachable content -- nothing cascades it, and the sweep cannot see it.
    op.execute(
        "DELETE FROM embeddings "
        "WHERE note_id IS NULL AND highlight_id IS NULL AND digest_id IS NULL"
    )
    op.drop_constraint(CONSTRAINT, "embeddings", type_="check")
    op.create_check_constraint(CONSTRAINT, "embeddings", _ANCHORED)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(CONSTRAINT, "embeddings", type_="check")
    op.create_check_constraint(CONSTRAINT, "embeddings", _ORIGINAL)
