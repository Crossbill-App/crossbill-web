"""DB-backed tests for SemanticSearchQuery via the SQLite Python fallback."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.infrastructure.notes.orm.associations import note_books
from src.infrastructure.semantic.queries.semantic_search_query import SemanticSearchQuery
from src.models import Book, Embedding, Highlight, Note, User
from tests.conftest import device_datetime

USER_ID = 1
OTHER_USER_ID = 2

#: Which cascade anchor each content type populates, as the repository sets it.
_ANCHOR_COLUMN = {
    ContentType.NOTE: "note_id",
    ContentType.HIGHLIGHT: "highlight_id",
}


async def _add_source(
    db: AsyncSession,
    content_type: ContentType,
    content_id: int,
    user_id: int,
    linked_book_ids: tuple[int, ...] = (),
) -> None:
    """Create the row the embedding's anchor points at.

    The anchor is a real foreign key and the CHECK requires it to be set, so an
    embedding cannot be planted for content that does not exist.
    """
    if content_type is ContentType.NOTE:
        db.add(Note(id=content_id, user_id=user_id, title=f"note {content_id}", body=""))
        await db.flush()
        for book_id in linked_book_ids:
            await db.execute(note_books.insert().values(note_id=content_id, book_id=book_id))
    else:
        book = Book(user_id=user_id, title=f"book for highlight {content_id}")
        db.add(book)
        await db.flush()
        db.add(
            Highlight(
                id=content_id,
                user_id=user_id,
                book_id=book.id,
                text=f"highlight {content_id}",
                datetime=device_datetime("2024-01-15 14:30:22"),
                content_hash="c" * 64,
            )
        )
    await db.flush()


async def _add_embedding(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
    vector: list[float],
    user_id: int = USER_ID,
    book_id: int | None = None,
    linked_book_ids: tuple[int, ...] = (),
) -> None:
    await _add_source(db, content_type, content_id, user_id, linked_book_ids)
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
            **{_ANCHOR_COLUMN[content_type]: content_id},
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

    async def test_filters_to_a_single_content_type(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        await _add_embedding(
            db_session, content_type=ContentType.NOTE, content_id=1, vector=[1.0, 0.0]
        )
        await _add_embedding(
            db_session, content_type=ContentType.HIGHLIGHT, content_id=2, vector=[1.0, 0.0]
        )

        hits = await query.nearest(
            embedding=[1.0, 0.0],
            user_id=USER_ID,
            book_id=None,
            limit=10,
            content_type=ContentType.NOTE,
        )

        assert [(hit.content_type, hit.content_id) for hit in hits] == [(ContentType.NOTE, 1)]

    async def test_scopes_notes_through_the_book_link_table(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        """A note linked to two books has a NULL embedding scope but is still in the book.

        ``embeddings.book_id`` stays NULL because no single book is the right
        answer. Filtering on that column would make this note unfindable by
        ``?book_id=``, which is the bug this scoping fixes.
        """
        wanted = Book(user_id=USER_ID, title="Wanted")
        other = Book(user_id=USER_ID, title="Other")
        db_session.add_all([wanted, other])
        await db_session.commit()
        await db_session.refresh(wanted)
        await db_session.refresh(other)

        await _add_embedding(
            db_session,
            content_type=ContentType.NOTE,
            content_id=1,
            vector=[1.0, 0.0],
            book_id=None,
            linked_book_ids=(wanted.id, other.id),
        )
        await _add_embedding(
            db_session,
            content_type=ContentType.NOTE,
            content_id=2,
            vector=[1.0, 0.0],
            book_id=None,
            linked_book_ids=(other.id,),
        )

        hits = await query.nearest(
            embedding=[1.0, 0.0],
            user_id=USER_ID,
            book_id=wanted.id,
            limit=10,
            content_type=ContentType.NOTE,
        )

        assert [hit.content_id for hit in hits] == [1]


class TestGetAnchor:
    async def test_round_trips_the_stored_vector_and_book(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        book = Book(user_id=USER_ID, title="Anchor's book")
        db_session.add(book)
        await db_session.flush()
        await _add_embedding(
            db_session,
            content_type=ContentType.NOTE,
            content_id=7,
            vector=[0.1, 0.2, 0.3],
            book_id=book.id,
        )

        anchor = await query.get_anchor(
            content_type=ContentType.NOTE, content_id=7, user_id=USER_ID
        )

        assert anchor is not None
        assert anchor.vector == [0.1, 0.2, 0.3]
        assert anchor.book_id == book.id

    async def test_carries_a_null_book(
        self, query: SemanticSearchQuery, db_session: AsyncSession
    ) -> None:
        """A note linked to zero or several books anchors with no book at all.

        The ranking rules read this to decide what counts as cross-book, so a
        NULL that arrived as a 0 would quietly make every neighbour same-book.
        """
        await _add_embedding(
            db_session, content_type=ContentType.NOTE, content_id=7, vector=[0.1, 0.2]
        )

        anchor = await query.get_anchor(
            content_type=ContentType.NOTE, content_id=7, user_id=USER_ID
        )

        assert anchor is not None
        assert anchor.book_id is None

    async def test_returns_none_when_absent(self, query: SemanticSearchQuery) -> None:
        assert (
            await query.get_anchor(content_type=ContentType.NOTE, content_id=99, user_id=USER_ID)
            is None
        )
