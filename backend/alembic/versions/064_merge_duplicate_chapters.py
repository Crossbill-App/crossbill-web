"""Merge duplicate chapter rows produced by ambiguous TOC parent resolution

Chapter sync used to resolve a TOC entry's parent by bare name, so re-uploading
an EPUB whose titles repeat could attach a run's chapters to a different parent
row than the previous run and re-create an entire subtree. Books also carry an
older duplicate shape: a legacy row (start_xpoint NULL) beside the modern row
the legacy-migration path never matched because the legacy row had a parent.

Both shapes look the same in the data: several rows sharing
(book_id, name, chapter_number), of which at most one distinct non-null
start_xpoint exists. Duplicates are not cosmetic -- chapter_number is an
identity for the ereader plugin's digest cache and for highlight upload, so a
twin silently misroutes highlights and rolls back cache writes.

For each such group one row is kept (the one carrying an xpoint, lowest id
first) and the others are merged into it: children, highlights, flashcards,
chat sessions and note links are repointed, the keeper's digest wins over the
twin's, and the twin row is deleted.

Note: repointing a dropped parent's children onto the keeper could in principle
collide with uq_chapter_per_book (book_id, parent_id, name) if the keeper
already had a same-named child from a different group. No such case exists in
the data this repairs; a collision would abort the migration in its transaction
rather than half-apply it.

Revision ID: 064
Revises: 063
"""

from collections.abc import Sequence

from alembic import op

revision: str = "064"
down_revision: str | Sequence[str] | None = "063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BUILD_MERGE_MAP = """
CREATE TEMP TABLE chapter_merge_map AS
WITH ranked AS (
    SELECT
        id,
        first_value(id) OVER (
            PARTITION BY book_id, name, chapter_number
            ORDER BY (start_xpoint IS NULL), id
        ) AS keeper_id,
        count(*) OVER (PARTITION BY book_id, name, chapter_number) AS group_size
    FROM chapters
)
SELECT id AS dropped_id, keeper_id
FROM ranked
WHERE group_size > 1 AND id <> keeper_id
"""

# Children first: chapters.parent_id cascades on delete, so a dropped parent
# would take its subtree with it. Only surviving children are repointed -- a
# dropped child is deleted anyway, and moving it under the keeper would collide
# with the twin already sitting there.
REPOINT_STATEMENTS = [
    """
    UPDATE chapters c SET parent_id = m.keeper_id
    FROM chapter_merge_map m
    WHERE c.parent_id = m.dropped_id
      AND NOT EXISTS (SELECT 1 FROM chapter_merge_map d WHERE d.dropped_id = c.id)
    """,
    """
    UPDATE highlights h SET chapter_id = m.keeper_id
    FROM chapter_merge_map m WHERE h.chapter_id = m.dropped_id
    """,
    """
    UPDATE flashcards f SET chapter_id = m.keeper_id
    FROM chapter_merge_map m WHERE f.chapter_id = m.dropped_id
    """,
    """
    UPDATE ai_chat_sessions s SET chapter_id = m.keeper_id
    FROM chapter_merge_map m WHERE s.chapter_id = m.dropped_id
    """,
    # note_chapters is keyed by (note_id, chapter_id): drop the links that would
    # collide with one the keeper already has, then move the rest.
    """
    DELETE FROM note_chapters n USING chapter_merge_map m
    WHERE n.chapter_id = m.dropped_id
      AND EXISTS (
          SELECT 1 FROM note_chapters existing
          WHERE existing.note_id = n.note_id AND existing.chapter_id = m.keeper_id
      )
    """,
    """
    UPDATE note_chapters n SET chapter_id = m.keeper_id
    FROM chapter_merge_map m WHERE n.chapter_id = m.dropped_id
    """,
    # chapter_digests is unique per chapter: the keeper's digest wins, and the
    # dropped digest's embeddings cascade away with it.
    """
    DELETE FROM chapter_digests d USING chapter_merge_map m
    WHERE d.chapter_id = m.dropped_id
      AND EXISTS (
          SELECT 1 FROM chapter_digests existing WHERE existing.chapter_id = m.keeper_id
      )
    """,
    """
    UPDATE chapter_digests d SET chapter_id = m.keeper_id
    FROM chapter_merge_map m WHERE d.chapter_id = m.dropped_id
    """,
    """
    DELETE FROM chapters c USING chapter_merge_map m WHERE c.id = m.dropped_id
    """,
]


def upgrade() -> None:
    op.execute(BUILD_MERGE_MAP)
    for statement in REPOINT_STATEMENTS:
        op.execute(statement)
    op.execute("DROP TABLE chapter_merge_map")


def downgrade() -> None:
    # Irreversible: the merged rows and their digests are gone.
    pass
