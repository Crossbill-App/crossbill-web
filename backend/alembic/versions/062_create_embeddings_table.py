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
        sa.Column("book_id", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint("content_type", "content_id", name="uq_embeddings_content"),
    )

    op.create_index("ix_embeddings_user_id", "embeddings", ["user_id"])
    op.create_index("ix_embeddings_content", "embeddings", ["content_type", "content_id"])
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
    op.drop_index("ix_embeddings_content", table_name="embeddings")
    op.drop_index("ix_embeddings_user_id", table_name="embeddings")
    op.drop_table("embeddings")
