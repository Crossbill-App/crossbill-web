"""Repository for content embeddings (upsert / get_state / delete_for)."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_repository import EmbeddingState, EmbeddingWrite
from src.infrastructure.common.sql import is_postgres
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM

_CONFLICT_KEYS = ["content_type", "content_id"]

#: Which cascade-anchor column each content type populates. The CHECK constraint
#: on the table requires exactly one to be set and to equal content_id.
_ANCHOR_COLUMN = {
    ContentType.NOTE: "note_id",
    ContentType.HIGHLIGHT: "highlight_id",
    ContentType.DIGEST: "digest_id",
}


def _anchors(content_type: ContentType, content_id: int) -> dict[str, int | None]:
    """Set this type's anchor column to content_id and null the other two."""
    return {
        column: (content_id if column == _ANCHOR_COLUMN[content_type] else None)
        for column in _ANCHOR_COLUMN.values()
    }


class EmbeddingRepository:
    """Upsert-style store for content embeddings keyed by (content_type, content_id)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_many(self, records: list[EmbeddingWrite]) -> None:
        if not records:
            return
        values = [
            {
                "user_id": record.user_id,
                "content_type": record.content_type.value,
                "content_id": record.content_id,
                "book_id": record.book_id,
                "embedding": record.embedding,
                "model_name": record.model_name,
                "model_version": record.model_version,
                "content_hash": record.content_hash,
                **_anchors(record.content_type, record.content_id),
            }
            for record in records
        ]

        insert = pg_insert if is_postgres(self.db) else sqlite_insert
        stmt = insert(EmbeddingORM).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=_CONFLICT_KEYS,
            # Read from the rejected row rather than from a captured record:
            # one statement carries many rows, so the update has to take each
            # row's own values. No anchors here — the conflict key is
            # (content_type, content_id) and the anchor is a function of exactly
            # those two, so the row being updated already carries the value this
            # would write.
            set_={
                "user_id": stmt.excluded.user_id,
                "book_id": stmt.excluded.book_id,
                "embedding": stmt.excluded.embedding,
                "model_name": stmt.excluded.model_name,
                "model_version": stmt.excluded.model_version,
                "content_hash": stmt.excluded.content_hash,
                "updated_at": func.now(),
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_states(
        self, content_type: ContentType, content_ids: list[int]
    ) -> dict[int, EmbeddingState]:
        if not content_ids:
            return {}
        stmt = select(
            EmbeddingORM.content_id,
            EmbeddingORM.content_hash,
            EmbeddingORM.model_name,
            EmbeddingORM.model_version,
        ).where(
            EmbeddingORM.content_type == content_type.value,
            EmbeddingORM.content_id.in_(content_ids),
        )
        rows = (await self.db.execute(stmt)).all()
        return {
            row.content_id: EmbeddingState(
                content_hash=row.content_hash,
                model_name=row.model_name,
                model_version=row.model_version,
            )
            for row in rows
        }

    async def delete_for(self, content_type: ContentType, content_ids: list[int]) -> None:
        if not content_ids:
            return
        stmt = delete(EmbeddingORM).where(
            EmbeddingORM.content_type == content_type.value,
            EmbeddingORM.content_id.in_(content_ids),
        )
        await self.db.execute(stmt)
        await self.db.commit()
