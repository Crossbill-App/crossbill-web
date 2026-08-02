"""Rename chapter_prereading_contents to chapter_digests

The artifact is read both before a chapter (to support skimming) and after it
as review, so naming it after one of its two uses was wrong. See CONTEXT.md.

Also renames the job_batches.batch_type value, which is stored as a plain
string, so existing rows have to be rewritten alongside the table.

Revision ID: 061
Revises: 060
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "061"
down_revision: str | Sequence[str] | None = "060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("chapter_prereading_contents", "chapter_digests")
    # rename_table leaves indexes and constraints under their original names.
    op.execute(
        sa.text(
            "ALTER INDEX ix_chapter_prereading_contents_chapter_id "
            "RENAME TO ix_chapter_digests_chapter_id"
        )
    )
    op.execute(
        sa.text("ALTER INDEX chapter_prereading_contents_pkey RENAME TO chapter_digests_pkey")
    )
    op.execute(
        sa.text(
            "ALTER TABLE chapter_digests RENAME CONSTRAINT "
            "chapter_prereading_contents_chapter_id_key TO chapter_digests_chapter_id_key"
        )
    )
    op.execute(
        sa.text(
            "UPDATE job_batches SET batch_type = 'chapter_digest' "
            "WHERE batch_type = 'chapter_prereading'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE job_batches SET batch_type = 'chapter_prereading' "
            "WHERE batch_type = 'chapter_digest'"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE chapter_digests RENAME CONSTRAINT "
            "chapter_digests_chapter_id_key TO chapter_prereading_contents_chapter_id_key"
        )
    )
    op.execute(
        sa.text("ALTER INDEX chapter_digests_pkey RENAME TO chapter_prereading_contents_pkey")
    )
    op.execute(
        sa.text(
            "ALTER INDEX ix_chapter_digests_chapter_id "
            "RENAME TO ix_chapter_prereading_contents_chapter_id"
        )
    )
    op.rename_table("chapter_digests", "chapter_prereading_contents")
