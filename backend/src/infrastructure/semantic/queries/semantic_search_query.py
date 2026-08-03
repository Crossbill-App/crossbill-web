"""Nearest-neighbour query adapter over the ``embeddings`` index.

On PostgreSQL the ranking is pushed into pgvector's ``<=>`` cosine-distance
operator with the HNSW index behind it. SQLite (the test suite) has no vector
type -- the column degrades to JSON -- so the same scan is computed in Python,
keeping the read path unit-testable off Postgres. Either way the adapter only
selects, filters and orders; no business rule lives here (ADR-0001 Rule 1).
"""

from math import sqrt

from sqlalchemy import Float, and_, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.semantic_search import SemanticSearchHit
from src.infrastructure.common.sql import is_postgres
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM

#: How many HNSW candidates to ask for per requested row.
#:
#: The index is global over ``embedding`` while every query filters by user
#: *after* the scan, so the candidate pool has to absorb other tenants' rows.
#: pgvector's default ``hnsw.ef_search`` is 40 -- below MAX_SEARCH_LIMIT, so a
#: limit of 50 could never be filled from an index scan at all, and a user whose
#: rows fall outside the global nearest-40 got a short answer with no error.
#: Four candidates per row is the usual starting point. This makes the failure
#: far less likely; it cannot make a post-filtered scan exact, and pgvector is
#: pinned at 0.5.0, so the iterative scan that would (0.8+) is unavailable.
EF_SEARCH_FACTOR = 4


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class SemanticSearchQuery:
    """Ranks a user's embeddings by cosine similarity to a query vector."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def nearest(
        self,
        *,
        embedding: list[float],
        user_id: int,
        book_id: int | None,
        limit: int,
        exclude: tuple[ContentType, int] | None = None,
    ) -> list[SemanticSearchHit]:
        filters = self._filters(user_id, book_id, exclude)
        if is_postgres(self.db):
            return await self._nearest_postgres(embedding, filters, limit)
        return await self._nearest_python(embedding, filters, limit)

    async def get_vector(
        self, *, content_type: ContentType, content_id: int, user_id: int
    ) -> list[float] | None:
        stmt = select(EmbeddingORM.embedding).where(
            EmbeddingORM.content_type == content_type.value,
            EmbeddingORM.content_id == content_id,
            EmbeddingORM.user_id == user_id,
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return [float(value) for value in row]

    def _filters(
        self, user_id: int, book_id: int | None, exclude: tuple[ContentType, int] | None
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [EmbeddingORM.user_id == user_id]
        if book_id is not None:
            filters.append(EmbeddingORM.book_id == book_id)
        if exclude is not None:
            exclude_type, exclude_id = exclude
            filters.append(
                not_(
                    and_(
                        EmbeddingORM.content_type == exclude_type.value,
                        EmbeddingORM.content_id == exclude_id,
                    )
                )
            )
        return filters

    async def _nearest_postgres(
        self, embedding: list[float], filters: list[ColumnElement[bool]], limit: int
    ) -> list[SemanticSearchHit]:
        # Transaction-scoped (the third argument), so widening the candidate
        # pool cannot leak into whatever else runs on this connection.
        await self.db.execute(
            select(func.set_config("hnsw.ef_search", str(limit * EF_SEARCH_FACTOR), True))
        )
        distance = EmbeddingORM.embedding.op("<=>", return_type=Float)(embedding)
        stmt = (
            select(
                EmbeddingORM.content_type,
                EmbeddingORM.content_id,
                EmbeddingORM.book_id,
                distance.label("distance"),
            )
            .where(*filters)
            # id breaks ties so equidistant rows cannot come back in a different
            # order on each call, or in a different order than the SQLite path.
            .order_by(distance.asc(), EmbeddingORM.id.asc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            _to_hit(row.content_type, row.content_id, row.book_id, 1.0 - row.distance)
            for row in rows
        ]

    async def _nearest_python(
        self, embedding: list[float], filters: list[ColumnElement[bool]], limit: int
    ) -> list[SemanticSearchHit]:
        stmt = select(
            EmbeddingORM.id,
            EmbeddingORM.content_type,
            EmbeddingORM.content_id,
            EmbeddingORM.book_id,
            EmbeddingORM.embedding,
        ).where(*filters)
        rows = (await self.db.execute(stmt)).all()
        scored = [(row, _cosine_similarity(embedding, list(row.embedding))) for row in rows]
        scored.sort(key=lambda pair: (-pair[1], pair[0].id))
        return [
            _to_hit(row.content_type, row.content_id, row.book_id, score)
            for row, score in scored[:limit]
        ]


def _to_hit(
    content_type: str, content_id: int, book_id: int | None, score: float
) -> SemanticSearchHit:
    return SemanticSearchHit(
        content_type=ContentType(content_type),
        content_id=content_id,
        book_id=book_id,
        score=score,
    )
