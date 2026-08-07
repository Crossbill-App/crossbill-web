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
from src.infrastructure.notes.orm.associations import note_books
from src.infrastructure.semantic.orm.embedding_model import Embedding as EmbeddingORM

#: Resume the HNSW scan when the ``user_id`` filter rejects its candidates.
#:
#: The index is global over ``embedding`` while every query filters by user
#: *after* the scan. Without this, the scan hands back its ``ef_search``
#: candidates once, the filter discards whatever belongs to other users, and the
#: query answers with the remainder -- which is *nothing at all* when another
#: user's rows sit between the query vector and this user's. Measured against
#: pgvector 0.8.6 on a 10k-row index with the searching user's rows behind that
#: noise: 0 rows returned with the scan off, the full 10 with it on.
#:
#: ``strict_order`` rather than ``relaxed_order``: relaxed hands back rows
#: slightly out of distance order, and the ``ORDER BY distance, id`` below would
#: not repair it -- the planner takes the index's ordering as given for the
#: leading key and only sorts within ties (an Incremental Sort). Ranking that
#: cannot silently reorder is worth more here than the speed difference over at
#: most ``MAX_SEARCH_LIMIT`` rows.
#:
#: Requires pgvector 0.8+, which the bundled ``pgvector/pgvector:pg18`` image
#: ships. Still not exact: ``hnsw.max_scan_tuples`` (default 20 000) bounds the
#: resumed scan, so a user whose rows sit behind more than that many of other
#: users' gets a short answer again. That moves the failure from "any busier
#: neighbour" to "a corpus far larger than this one".
HNSW_ITERATIVE_SCAN = "strict_order"

#: How many HNSW candidates to ask for per requested row on the first pass.
#:
#: pgvector's default ``hnsw.ef_search`` is 40 -- below MAX_SEARCH_LIMIT, so a
#: limit of 50 could not be filled from one pass at all. Recall no longer rests
#: on this number, though: the iterative scan above resumes until the limit is
#: met, so this only trades a wider first pass for fewer resumptions.
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
        content_type: ContentType | None = None,
        exclude: tuple[ContentType, int] | None = None,
    ) -> list[SemanticSearchHit]:
        filters = self._filters(user_id, book_id, content_type, exclude)
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
        self,
        user_id: int,
        book_id: int | None,
        content_type: ContentType | None,
        exclude: tuple[ContentType, int] | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [EmbeddingORM.user_id == user_id]
        if content_type is not None:
            filters.append(EmbeddingORM.content_type == content_type.value)
        if book_id is not None:
            filters.append(self._book_filter(book_id, content_type))
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

    def _book_filter(self, book_id: int, content_type: ContentType | None) -> ColumnElement[bool]:
        """Scope to a book -- through ``note_books`` when the scan is notes only.

        ``embeddings.book_id`` is NULL for a note linked to zero or several
        books, because no single value is correct and picking one would make
        ``?book_id=`` depend on link order. Filtering notes on that column
        therefore cannot find such a note at all. ADR-0002 kept the link table
        out of the ranking query to hold it clear of other modules' tables; that
        cost is bounded now the note scan is its own statement.
        """
        if content_type is not ContentType.NOTE:
            return EmbeddingORM.book_id == book_id
        return EmbeddingORM.content_id.in_(
            select(note_books.c.note_id).where(note_books.c.book_id == book_id)
        )

    async def _nearest_postgres(
        self, embedding: list[float], filters: list[ColumnElement[bool]], limit: int
    ) -> list[SemanticSearchHit]:
        # Transaction-scoped (the third argument), so neither the scan mode nor
        # the widened candidate pool leaks into whatever else runs on this
        # connection. One statement for both: they are always set together.
        await self.db.execute(
            select(
                func.set_config("hnsw.iterative_scan", HNSW_ITERATIVE_SCAN, True),
                func.set_config("hnsw.ef_search", str(limit * EF_SEARCH_FACTOR), True),
            )
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
