"""DB-backed tests for SemanticSearchQuery via the SQLite Python fallback."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.infrastructure.semantic.queries.semantic_search_query import SemanticSearchQuery
from src.models import Book, Embedding, User

USER_ID = 1
OTHER_USER_ID = 2


async def _add_embedding(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
    vector: list[float],
    user_id: int = USER_ID,
    book_id: int | None = None,
) -> None:
    db.add(
        Embedding(
            user_id=user_id,
            content_type=content_type.value,
            content_id=content_id,
            book_id=book_id,
            embedding=vector,
            model_name="bge-m3",
            model_version="1",
            content_hash="h" * 64,
        )
    )
    await db.commit()


async def _seed_notes(db: AsyncSession, vectors: dict[int, list[float]]) -> None:
    for content_id, vector in vectors.items():
        await _add_embedding(
            db, content_type=ContentType.NOTE, content_id=content_id, vector=vector
        )


@pytest.fixture
def query(db_session: AsyncSession) -> SemanticSearchQuery:
    return SemanticSearchQuery(db_session)


class TestNearest:
    async def test_ranks_by_cosine_similarity(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        await _seed_notes(db_session, {1: [1.0, 0.0], 2: [0.7, 0.7], 3: [0.0, 1.0]})

        hits = await query.nearest(embedding=[1.0, 0.0], user_id=USER_ID, book_id=None, limit=10)

        assert [hit.content_id for hit in hits] == [1, 2, 3]
        assert hits[0].score == pytest.approx(1.0)
        assert hits[0].score >= hits[1].score >= hits[2].score

    async def test_respects_limit(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        await _seed_notes(db_session, {1: [1.0, 0.0], 2: [0.9, 0.1], 3: [0.0, 1.0]})

        hits = await query.nearest(embedding=[1.0, 0.0], user_id=USER_ID, book_id=None, limit=2)

        assert [hit.content_id for hit in hits] == [1, 2]

    async def test_scopes_to_user(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
        await db_session.commit()
        await _add_embedding(
            db_session, content_type=ContentType.NOTE, content_id=1, vector=[1.0, 0.0]
        )
        await _add_embedding(
            db_session,
            content_type=ContentType.NOTE,
            content_id=2,
            vector=[1.0, 0.0],
            user_id=OTHER_USER_ID,
        )

        hits = await query.nearest(embedding=[1.0, 0.0], user_id=USER_ID, book_id=None, limit=10)

        assert [hit.content_id for hit in hits] == [1]

    async def test_scopes_to_book(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        # embeddings.book_id is a real FK, so the books have to exist.
        db_session.add_all(
            [
                Book(id=10, user_id=USER_ID, title="Scoped"),
                Book(id=20, user_id=USER_ID, title="Other"),
            ]
        )
        await db_session.commit()
        await _add_embedding(
            db_session, content_type=ContentType.NOTE, content_id=1, vector=[1.0, 0.0], book_id=10
        )
        await _add_embedding(
            db_session, content_type=ContentType.NOTE, content_id=2, vector=[1.0, 0.0], book_id=20
        )

        hits = await query.nearest(embedding=[1.0, 0.0], user_id=USER_ID, book_id=10, limit=10)

        assert [hit.content_id for hit in hits] == [1]

    async def test_excludes_the_given_unit(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        await _add_embedding(
            db_session, content_type=ContentType.HIGHLIGHT, content_id=1, vector=[1.0, 0.0]
        )
        await _add_embedding(
            db_session, content_type=ContentType.NOTE, content_id=1, vector=[0.9, 0.1]
        )

        hits = await query.nearest(
            embedding=[1.0, 0.0],
            user_id=USER_ID,
            book_id=None,
            limit=10,
            exclude=(ContentType.HIGHLIGHT, 1),
        )

        assert [(hit.content_type, hit.content_id) for hit in hits] == [(ContentType.NOTE, 1)]


class TestGetVector:
    async def test_round_trips_the_stored_vector(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        await _add_embedding(
            db_session, content_type=ContentType.NOTE, content_id=7, vector=[0.1, 0.2, 0.3]
        )

        vector = await query.get_vector(
            content_type=ContentType.NOTE, content_id=7, user_id=USER_ID
        )

        assert vector == [0.1, 0.2, 0.3]

    async def test_returns_none_when_absent(self, query: SemanticSearchQuery) -> None:
        assert (
            await query.get_vector(content_type=ContentType.NOTE, content_id=99, user_id=USER_ID)
            is None
        )
