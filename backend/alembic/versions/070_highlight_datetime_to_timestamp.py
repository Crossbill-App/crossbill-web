"""Store highlight device timestamps as timestamps, not KOReader strings

``datetime`` and ``koreader_updated_at`` arrived as KOReader's own
``yyyy-MM-dd HH:mm:ss`` text and were passed through unnormalised, so the web
client needed a bespoke parser for them while every other timestamp the API
sends is ISO (#664). They become ``TIMESTAMP WITHOUT TIME ZONE``: KOReader
writes device-local wall time with no offset, and none is invented here.

Existing rows are converted in place. Deduplication keys on ``content_hash``
alone, so rewriting these columns cannot make a re-sync look like new
highlights. A ``datetime`` that does not parse falls back to the row's
``created_at`` -- the insert time of the sync that carried it, which is a real
instant and always present -- because the column is NOT NULL; an unparseable
``koreader_updated_at`` becomes NULL, which reads as "never edited on a
device".

Revision ID: 070
Revises: 069
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "070"
down_revision: str | Sequence[str] | None = "069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Postgres' own ``timestamp`` cast accepts both the KOReader separator and the
# ISO one, so the guard only has to reject text that is not a timestamp at all.
_TIMESTAMP_TEXT = r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"

UPGRADE_DATETIME = f"""
ALTER TABLE highlights
    ALTER COLUMN datetime TYPE TIMESTAMP WITHOUT TIME ZONE
    USING CASE
        WHEN datetime ~ '{_TIMESTAMP_TEXT}' THEN datetime::timestamp
        ELSE created_at AT TIME ZONE 'UTC'
    END
"""

UPGRADE_UPDATED_AT = f"""
ALTER TABLE highlights
    ALTER COLUMN koreader_updated_at TYPE TIMESTAMP WITHOUT TIME ZONE
    USING CASE
        WHEN koreader_updated_at ~ '{_TIMESTAMP_TEXT}' THEN koreader_updated_at::timestamp
    END
"""

DOWNGRADE_DATETIME = """
ALTER TABLE highlights
    ALTER COLUMN datetime TYPE VARCHAR(50)
    USING to_char(datetime, 'YYYY-MM-DD HH24:MI:SS')
"""

DOWNGRADE_UPDATED_AT = """
ALTER TABLE highlights
    ALTER COLUMN koreader_updated_at TYPE VARCHAR(50)
    USING to_char(koreader_updated_at, 'YYYY-MM-DD HH24:MI:SS')
"""


def upgrade() -> None:
    op.execute(sa.text(UPGRADE_DATETIME))
    op.execute(sa.text(UPGRADE_UPDATED_AT))


def downgrade() -> None:
    op.execute(sa.text(DOWNGRADE_DATETIME))
    op.execute(sa.text(DOWNGRADE_UPDATED_AT))
