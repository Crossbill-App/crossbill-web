"""The one statement a position write is, and what it guarantees under a race.

Tested here rather than through the endpoint because the guarantee is about two
requests arriving at once, and the API tier shares one database session across a
test -- two real requests in flight would be two coroutines fighting over one
connection, which is a different bug from the one under test.

What these assert is the mechanism the endpoint's safety rests on: the write is
an upsert whose update is conditional, so *both* questions it depends on -- is
there a row yet, and is this newer than what is in it -- are answered at the
moment of writing rather than a round trip earlier. Two tabs turning pages
independently used to be a duplicate-key error and an orphaned reading session.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects import BookId, ReadingSessionId, UserId, XPoint
from src.domain.common.value_objects.position import Position
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition
from src.infrastructure.reading.orm.reading_session_model import (
    ReadingSession as ReadingSessionORM,
)
from src.infrastructure.web_reader.orm.web_reading_position_model import (
    WebReadingPosition as WebReadingPositionORM,
)
from src.infrastructure.web_reader.repositories.web_reading_position_repository import (
    WebReadingPositionRepository,
)
from src.models import Book
from tests.conftest import create_test_book

FIRST = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
XPOINT = "/body/DocFragment[1]/body/div[1]/p[1]"


@pytest.fixture
async def book(db_session: AsyncSession) -> Book:
    return await create_test_book(db_session=db_session, user_id=1, title="Raced Book")


@pytest.fixture
def positions(db_session: AsyncSession) -> WebReadingPositionRepository:
    return WebReadingPositionRepository(db_session)


def a_position(book: Book, at: datetime, page: int = 1) -> WebReadingPosition:
    """A position for the default user, distinguishable by ``page``."""
    return WebReadingPosition.create(
        user_id=UserId(1),
        book_id=BookId(book.id),
        locator={"href": "OEBPS/chapter1.xhtml", "type": "x", "locations": {"position": page}},
        xpoint=XPoint.parse(XPOINT),
        recorded_at=at,
        position=Position(index=page, char_index=0),
    )


async def a_session(db_session: AsyncSession, book: Book, tag: str) -> ReadingSessionId:
    """A real reading session row, because the pointer is a foreign key."""
    session = ReadingSessionORM(
        user_id=1,
        book_id=book.id,
        start_time=FIRST,
        end_time=FIRST,
        content_hash=f"hash-{tag}",
    )
    db_session.add(session)
    await db_session.commit()
    return ReadingSessionId(session.id)


async def row_count(db_session: AsyncSession) -> int:
    return (await db_session.execute(select(func.count(WebReadingPositionORM.id)))).scalar_one()


class TestRecordingAPosition:
    """One row per reader and book, however many writers there are."""

    async def test_the_first_write_creates_the_row(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        """Should insert, and report that no session was open before it."""
        recorded = await positions.record(a_position(book, FIRST))

        assert recorded is not None
        assert recorded.was_open is None
        assert recorded.position.position == Position(index=1, char_index=0)
        assert await row_count(db_session) == 1

    async def test_a_second_first_write_updates_rather_than_collides(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        """Should absorb a second write that also believed the row did not exist.

        This is the race: two tabs opened together both find nothing stored and
        both go on to write. As a plain insert the second was a unique-constraint
        violation -- a 500 for the reader, and a reading session already
        committed with nothing left pointing at it.
        """
        await positions.record(a_position(book, FIRST))

        second = await positions.record(a_position(book, FIRST + timedelta(seconds=1), page=2))

        assert second is not None
        assert second.position.position == Position(index=2, char_index=0)
        assert await row_count(db_session) == 1

    async def test_an_older_write_changes_nothing(
        self, positions: WebReadingPositionRepository, book: Book
    ) -> None:
        """Should refuse to overwrite a newer position with an older one, and say so.

        ``None`` rather than an exception: the caller answers an overtaken write
        with what is stored. What matters is that it hears it *before* writing a
        reading session, which is why this is the first write the endpoint makes.
        """
        await positions.record(a_position(book, FIRST + timedelta(minutes=5), page=9))

        overtaken = await positions.record(a_position(book, FIRST, page=1))

        assert overtaken is None
        stored = await positions.find_for_book(BookId(book.id), UserId(1))
        assert stored is not None
        assert stored.position == Position(index=9, char_index=0)

    async def test_the_row_reports_the_session_that_was_open_before_it(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        """Should hand back the pointer as it was, which is what decides the sitting."""
        opened = await a_session(db_session, book, "open")
        first = await positions.record(a_position(book, FIRST))
        assert first is not None
        await positions.attach_session(first.position, opened, FIRST)

        later = await positions.record(a_position(book, FIRST + timedelta(minutes=1), page=2))

        assert later is not None
        assert later.was_open == opened


class TestClaimingTheSessionPointer:
    """Only the writer that is still the latest may move the open-session pointer."""

    async def test_the_latest_writer_may_point_the_row_at_its_session(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        """Should attach the session when nothing has overtaken the write."""
        mine = await a_session(db_session, book, "mine")
        recorded = await positions.record(a_position(book, FIRST))
        assert recorded is not None

        await positions.attach_session(recorded.position, mine, FIRST)

        stored = await positions.find_for_book(BookId(book.id), UserId(1))
        assert stored is not None
        assert stored.reading_session_id == mine

    async def test_an_overtaken_writer_may_not(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        """Should leave the pointer alone once a later write has landed.

        This is what stops a close undoing a page turn that arrived after it,
        and a page turn reopening a session that was closed after it: the
        pointer only ever reflects whichever write is currently the latest.
        """
        winner = await a_session(db_session, book, "winner")
        loser = await a_session(db_session, book, "loser")
        first = await positions.record(a_position(book, FIRST))
        assert first is not None
        later = await positions.record(a_position(book, FIRST + timedelta(minutes=1), page=2))
        assert later is not None
        await positions.attach_session(later.position, winner, later.position.updated_at)

        # The earlier request finally gets round to attaching its own session.
        await positions.attach_session(first.position, loser, FIRST)

        stored = await positions.find_for_book(BookId(book.id), UserId(1))
        assert stored is not None
        assert stored.reading_session_id == winner
