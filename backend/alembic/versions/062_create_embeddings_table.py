"""Create embeddings table for semantic search.

Revision ID: 062
Revises: 061
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "062"
down_revision: str | Sequence[str] | None = "061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed to bge-m3 (1024) and mirrors EMBEDDING_DIMENSIONS. A dimension change is
# a new migration + full backfill by design, not an in-place alter.
EMBEDDING_DIMENSIONS = 1024


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        # content_type + content_id stays the logical key, but a polymorphic id
        # cannot carry a constraint, so deleting a note or a digest would leave
        # its embedding orphaned. These three columns exist purely as cascade
        # anchors: exactly one is set, it always equals content_id (enforced by
        # the CHECK below), and the database prunes the row when its source goes.
        sa.Column(
            "note_id",
            sa.Integer(),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "highlight_id",
            sa.Integer(),
            sa.ForeignKey("highlights.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "digest_id",
            sa.Integer(),
            sa.ForeignKey("chapter_digests.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # SET NULL, not CASCADE: book_id is a scoping hint, not identity. A note
        # can outlive the book it was linked to, and deleting that book must
        # clear the scope rather than drop a live note's embedding. Content that
        # genuinely dies with the book is cascaded by the typed FKs above.
        sa.Column(
            "book_id",
            sa.Integer(),
            sa.ForeignKey("books.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # This also provides the lookup index for (content_type, content_id) --
        # a unique constraint is backed by a unique index, so a separate one
        # would only add write cost.
        sa.UniqueConstraint("content_type", "content_id", name="uq_embeddings_content"),
        # Keeps the anchor columns from drifting out of step with the logical
        # key: exactly one typed id is set, and it matches content_id.
        sa.CheckConstraint(
            "(content_type = 'note' AND note_id = content_id "
            "AND highlight_id IS NULL AND digest_id IS NULL) OR "
            "(content_type = 'highlight' AND highlight_id = content_id "
            "AND note_id IS NULL AND digest_id IS NULL) OR "
            "(content_type = 'digest' AND digest_id = content_id "
            "AND note_id IS NULL AND highlight_id IS NULL)",
            name="ck_embeddings_one_typed_id",
        ),
    )

    op.create_index("ix_embeddings_user_id", "embeddings", ["user_id"])
    # Postgres does not index FK columns automatically, so every cascading
    # delete would seq-scan this table. Partial: each column is set on only the
    # rows of its own content type.
    op.create_index("ix_embeddings_book_id", "embeddings", ["book_id"])
    for column in ("note_id", "highlight_id", "digest_id"):
        op.create_index(
            f"ix_embeddings_{column}",
            "embeddings",
            [column],
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )
    op.create_index(
        "ix_embeddings_embedding_hnsw",
        "embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_embeddings_embedding_hnsw", table_name="embeddings")
    for column in ("digest_id", "highlight_id", "note_id"):
        op.drop_index(f"ix_embeddings_{column}", table_name="embeddings")
    op.drop_index("ix_embeddings_book_id", table_name="embeddings")
    op.drop_index("ix_embeddings_user_id", table_name="embeddings")
    op.drop_table("embeddings")
