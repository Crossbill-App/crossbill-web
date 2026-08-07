"""Adapter tests for the two SearchHydrationQuery rules the API tier cannot reach.

Field mapping, ranking order, soft-delete drops and book scoping are all
asserted through ``/semantic/search`` in ``tests/test_semantic_search_api.py``,
so they are not repeated here. What is left needs shapes the endpoint cannot
produce: a hit whose source row is gone (the scan's own ``user_id`` filter and
the embeddings' FK cascade prevent it end to end) and an embedding of mine
pointing at another user's note or digest.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.semantic_search import SemanticSearchHit
from src.infrastructure.semantic.queries.search_hydration_query import SearchHydrationQuery
from src.models import Book, Chapter, ChapterDigest, Note, User

USER_ID = 1
OTHER_USER_ID = 2


def _hit(content_type: ContentType, content_id: int, score: float) -> SemanticSearchHit:
    return SemanticSearchHit(
        content_type=content_type, content_id=content_id, book_id=None, score=score
    )


@pytest.fixture
async def users(db_session: AsyncSession) -> None:
    # db_session already seeds User(id=1); only the stranger needs adding here.
    db_session.add(User(id=OTHER_USER_ID, email="stranger@test.com"))
    await db_session.commit()


@pytest.fixture
def query(db_session: AsyncSession) -> SearchHydrationQuery:
    return SearchHydrationQuery(db_session)


async def _add_digest(db: AsyncSession, book: Book) -> ChapterDigest:
    chapter = Chapter(book_id=book.id, name="Chapter One", chapter_number=1)
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    row = ChapterDigest(
        chapter_id=chapter.id,
        summary="What happened",
        keypoints=["first", "second"],
        questions=[],
        generated_at=datetime.now(UTC),
        ai_model="test",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


class TestOwnership:
    """The user_id filter each method re-asserts, rather than trusting the scan."""

    async def test_drops_another_users_note(
        self, query: SearchHydrationQuery, db_session: AsyncSession, users: None
    ) -> None:
        theirs = Note(user_id=OTHER_USER_ID, title="Theirs", body="the body", kind="concept")
        db_session.add(theirs)
        await db_session.commit()
        await db_session.refresh(theirs)

        views = await query.notes([_hit(ContentType.NOTE, theirs.id, 0.8)], USER_ID)

        assert views == ()

    async def test_drops_a_digest_under_another_users_book(
        self, query: SearchHydrationQuery, db_session: AsyncSession, users: None
    ) -> None:
        """A digest has no user_id of its own; ownership rides on the book."""
        their_book = Book(user_id=OTHER_USER_ID, title="Theirs")
        db_session.add(their_book)
        await db_session.commit()
        await db_session.refresh(their_book)
        digest = await _add_digest(db_session, their_book)

        views = await query.digests([_hit(ContentType.DIGEST, digest.id, 0.7)], USER_ID)

        assert views == ()


class TestMissingSources:
    async def test_every_type_drops_a_hit_whose_row_is_gone(
        self, query: SearchHydrationQuery, users: None
    ) -> None:
        """The drop rule, not the FK cascade, is what keeps deleted content out.

        A hard-deleted note or digest normally takes its embedding with it, but
        the guarantee cannot rest on that having fired.
        """
        assert await query.highlights([_hit(ContentType.HIGHLIGHT, 999, 0.9)], USER_ID) == ()
        assert await query.notes([_hit(ContentType.NOTE, 999, 0.9)], USER_ID) == ()
        assert await query.digests([_hit(ContentType.DIGEST, 999, 0.9)], USER_ID) == ()
