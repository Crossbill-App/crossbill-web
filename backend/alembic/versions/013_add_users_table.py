"""Add users table and associate existing data with admin user.

Revision ID: 013
Revises: 012
Create Date: 2025-11-23 00:00:00.000000

"""

import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add users table and user_id to books, highlights, highlight_tags, and tags."""
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_name"), "users", ["name"], unique=False)

    # 2. Insert default admin user
    # Use ADMIN_USERNAME from environment or default to 'admin'
    admin_username = os.getenv("ADMIN_USERNAME") or "admin"
    op.execute(
        sa.text("INSERT INTO users (id, name) VALUES (1, :username)").bindparams(
            username=admin_username
        )
    )

    # 3. Add user_id columns (nullable first to allow migration of existing data)
    op.add_column("books", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("tags", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("highlights", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("highlight_tags", sa.Column("user_id", sa.Integer(), nullable=True))

    # 4. Migrate existing data to admin user (user_id=1)
    op.execute(sa.text("UPDATE books SET user_id = 1 WHERE user_id IS NULL"))
    op.execute(sa.text("UPDATE tags SET user_id = 1 WHERE user_id IS NULL"))
    op.execute(sa.text("UPDATE highlights SET user_id = 1 WHERE user_id IS NULL"))
    op.execute(sa.text("UPDATE highlight_tags SET user_id = 1 WHERE user_id IS NULL"))

    # 5. Make user_id columns NOT NULL
    op.alter_column("books", "user_id", nullable=False)
    op.alter_column("tags", "user_id", nullable=False)
    op.alter_column("highlights", "user_id", nullable=False)
    op.alter_column("highlight_tags", "user_id", nullable=False)

    # 6. Add foreign key constraints
    op.create_foreign_key(
        "fk_books_user_id", "books", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_tags_user_id", "tags", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_highlights_user_id", "highlights", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_highlight_tags_user_id",
        "highlight_tags",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 7. Update unique constraints
    # Tags: Drop old unique index and constraint on name, add new (user_id, name)
    # The original migration created both a unique constraint and a unique index
    op.drop_index("ix_tags_name", table_name="tags")
    op.create_unique_constraint("uq_tag_user_name", "tags", ["user_id", "name"])

    # HighlightTags: Drop old constraint (book_id, name), add new (user_id, book_id, name)
    op.drop_constraint("uq_highlight_tag_book_name", "highlight_tags", type_="unique")
    op.create_unique_constraint(
        "uq_highlight_tag_user_book_name", "highlight_tags", ["user_id", "book_id", "name"]
    )

    # 8. Add indexes for user_id columns
    op.create_index(op.f("ix_books_user_id"), "books", ["user_id"], unique=False)
    op.create_index(op.f("ix_tags_user_id"), "tags", ["user_id"], unique=False)
    op.create_index(op.f("ix_highlights_user_id"), "highlights", ["user_id"], unique=False)
    op.create_index(op.f("ix_highlight_tags_user_id"), "highlight_tags", ["user_id"], unique=False)


def downgrade() -> None:
    """Remove users table and user_id from all tables."""
    # Remove indexes
    op.drop_index(op.f("ix_highlight_tags_user_id"), table_name="highlight_tags")
    op.drop_index(op.f("ix_highlights_user_id"), table_name="highlights")
    op.drop_index(op.f("ix_tags_user_id"), table_name="tags")
    op.drop_index(op.f("ix_books_user_id"), table_name="books")

    # Restore old constraints
    op.drop_constraint("uq_highlight_tag_user_book_name", "highlight_tags", type_="unique")
    op.create_unique_constraint("uq_highlight_tag_book_name", "highlight_tags", ["book_id", "name"])

    op.drop_constraint("uq_tag_user_name", "tags", type_="unique")
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    # Remove foreign keys
    op.drop_constraint("fk_highlight_tags_user_id", "highlight_tags", type_="foreignkey")
    op.drop_constraint("fk_highlights_user_id", "highlights", type_="foreignkey")
    op.drop_constraint("fk_tags_user_id", "tags", type_="foreignkey")
    op.drop_constraint("fk_books_user_id", "books", type_="foreignkey")

    # Remove user_id columns
    op.drop_column("highlight_tags", "user_id")
    op.drop_column("highlights", "user_id")
    op.drop_column("tags", "user_id")
    op.drop_column("books", "user_id")

    # Drop users table
    op.drop_index(op.f("ix_users_name"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
