"""Repository for content embeddings (upsert / get_state / delete_for)."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_repository import EmbeddingState, EmbeddingWrite
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM

_CONFLICT_KEYS = ["content_type", "content_id"]


class EmbeddingRepository:
    """Upsert-style store for content embeddings keyed by (content_type, content_id)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(self, record: EmbeddingWrite) -> None:
        values = {
            "user_id": record.user_id,
            "content_type": record.content_type.value,
            "content_id": record.content_id,
            "book_id": record.book_id,
            "embedding": record.embedding,
            "model_name": record.model_name,
            "model_version": record.model_version,
            "content_hash": record.content_hash,
        }
        updates = {
            "user_id": record.user_id,
            "book_id": record.book_id,
            "embedding": record.embedding,
            "model_name": record.model_name,
            "model_version": record.model_version,
            "content_hash": record.content_hash,
            "updated_at": func.now(),
        }

        insert = pg_insert if self.db.bind.dialect.name == "postgresql" else sqlite_insert
        stmt = insert(EmbeddingORM).values(values)
        stmt = stmt.on_conflict_do_update(index_elements=_CONFLICT_KEYS, set_=updates)
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_state(self, content_type: ContentType, content_id: int) -> EmbeddingState | None:
        stmt = select(
            EmbeddingORM.content_hash,
            EmbeddingORM.model_name,
            EmbeddingORM.model_version,
        ).where(
            EmbeddingORM.content_type == content_type.value,
            EmbeddingORM.content_id == content_id,
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None
        return EmbeddingState(
            content_hash=row.content_hash,
            model_name=row.model_name,
            model_version=row.model_version,
        )

    async def delete_for(self, content_type: ContentType, content_id: int) -> None:
        stmt = delete(EmbeddingORM).where(
            EmbeddingORM.content_type == content_type.value,
            EmbeddingORM.content_id == content_id,
        )
        await self.db.execute(stmt)
        await self.db.commit()
