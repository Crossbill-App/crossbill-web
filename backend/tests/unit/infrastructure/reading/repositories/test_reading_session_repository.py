"""Writing one session repeatedly, which is how a session read in the browser is recorded.

Every other write of a reading session is a bulk insert of finished sittings, so
these two are tested here rather than through an endpoint that has them.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.time import as_aware
from src.domain.common.value_objects import BookId, ReadingSessionId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.reading.entities.reading_session import ReadingSession
from src.domain.reading.exceptions import ReadingSessionNotFoundError
from src.infrastructure.reading.orm.reading_session_model import (
    ReadingSession as ReadingSessionORM,
)
from src.infrastructure.reading.repositories.reading_session_repository import (
    ReadingSessionRepository,
)
from src.models import Book, User

STARTED = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
READER = UserId(1)
OTHER_READER = UserId(2)


@pytest.fixture
def sessions(db_session: AsyncSession) -> ReadingSessionRepository:
    return ReadingSessionRepository(db_session)


def a_session(book: Book, reader: UserId = READER) -> ReadingSession:
    return ReadingSession.create(
        user_id=reader,
        book_id=BookId(book.id),
        start_time=STARTED,
        end_time=STARTED,
        start_page=3,
        end_page=3,
        end_position=Position(index=3),
    )


async def row_count(db_session: AsyncSession) -> int:
    return (await db_session.execute(select(func.count(ReadingSessionORM.id)))).scalar_one()


class TestSavingASession:
    async def test_a_session_with_no_id_yet_is_inserted(
        self, sessions: ReadingSessionRepository, test_book: Book, db_session: AsyncSession
    ) -> None:
        saved = await sessions.save(a_session(test_book))

        assert saved.id.value > 0
        assert saved.book_id == BookId(test_book.id)
        assert saved.end_page == 3
        assert await row_count(db_session) == 1

    async def test_saving_an_extended_session_rewrites_its_own_row(
        self, sessions: ReadingSessionRepository, test_book: Book, db_session: AsyncSession
    ) -> None:
        """The web reader writes one session as the reading goes on, not one per write."""
        opened = await sessions.save(a_session(test_book))

        opened.extend_to(STARTED + timedelta(minutes=20), position=Position(index=41), page=12)
        saved = await sessions.save(opened)

        assert saved.id == opened.id
        assert await row_count(db_session) == 1
        # Reads the row rather than the instance `save` just mutated, which the session
        # would otherwise hand back from its identity map.
        db_session.expunge_all()
        stored = await sessions.find_by_id(opened.id, READER)
        assert stored is not None
        assert as_aware(stored.end_time) == STARTED + timedelta(minutes=20)
        assert stored.end_position == Position(index=41)
        assert stored.end_page == 12

    async def test_extending_a_session_leaves_the_identity_it_deduplicates_on(
        self, sessions: ReadingSessionRepository, test_book: Book, db_session: AsyncSession
    ) -> None:
        """Nothing `content_hash` is built from changes as a sitting is extended.

        Reloaded first, the way a later write finds the session it is continuing: that is
        the path where the store has dropped the zone the hash was first built from.
        """
        opened = await sessions.save(a_session(test_book))
        original = (
            await db_session.execute(
                select(ReadingSessionORM.content_hash).where(
                    ReadingSessionORM.id == opened.id.value
                )
            )
        ).scalar_one()

        db_session.expunge_all()
        reloaded = await sessions.find_by_id(opened.id, READER)
        assert reloaded is not None
        reloaded.extend_to(STARTED + timedelta(minutes=20), position=Position(index=41))
        await sessions.save(reloaded)

        rewritten = (
            await db_session.execute(
                select(ReadingSessionORM.content_hash).where(
                    ReadingSessionORM.id == opened.id.value
                )
            )
        ).scalar_one()
        assert rewritten == original

    async def test_saving_a_session_that_is_gone_is_refused(
        self, sessions: ReadingSessionRepository, test_book: Book
    ) -> None:
        """Not silently re-inserted under the id it claims: the row it names was deleted."""
        vanished = a_session(test_book)
        vanished.id = ReadingSessionId(4242)

        with pytest.raises(ReadingSessionNotFoundError):
            await sessions.save(vanished)


class TestFindingASessionById:
    async def test_the_readers_own_session_is_returned(
        self, sessions: ReadingSessionRepository, test_book: Book
    ) -> None:
        saved = await sessions.save(a_session(test_book))

        found = await sessions.find_by_id(saved.id, READER)

        assert found is not None
        assert found.id == saved.id
        assert found.start_page == 3

    async def test_another_readers_session_reads_as_absent(
        self, sessions: ReadingSessionRepository, test_book: Book, db_session: AsyncSession
    ) -> None:
        db_session.add(User(id=OTHER_READER.value, email="other@test.com"))
        await db_session.commit()
        theirs = await sessions.save(a_session(test_book, reader=OTHER_READER))

        assert await sessions.find_by_id(theirs.id, READER) is None

    async def test_an_id_nobody_has_reads_as_absent(
        self, sessions: ReadingSessionRepository
    ) -> None:
        assert await sessions.find_by_id(ReadingSessionId(4242), READER) is None
