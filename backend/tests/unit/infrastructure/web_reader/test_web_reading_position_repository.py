"""The one statement a position write is, and what it guarantees under a race.

Tested here rather than through an endpoint because the guarantee is about two
requests arriving at once, and the API tier shares one database session across a
test -- two real requests in flight would be two coroutines fighting over one
connection, which is a different bug from the one under test.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
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
from src.models import Book, User
from tests.conftest import create_test_book

FIRST = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
READER = UserId(1)
OTHER_READER = UserId(2)


@pytest.fixture
async def book(db_session: AsyncSession) -> Book:
    return await create_test_book(db_session=db_session, user_id=1, title="Raced Book")


@pytest.fixture
def positions(db_session: AsyncSession) -> WebReadingPositionRepository:
    return WebReadingPositionRepository(db_session)


@pytest.fixture
async def recorded(positions: WebReadingPositionRepository, book: Book) -> WebReadingPosition:
    """Stored with its two clocks apart, so a guard on the wrong one cannot pass."""
    written = await positions.record(a_position(book, FIRST, observed=FIRST - timedelta(minutes=5)))
    assert written is not None
    return written.position


def a_position(
    book: Book,
    at: datetime,
    page: int = 1,
    observed: datetime | None = None,
    reader: UserId = READER,
) -> WebReadingPosition:
    """A position distinguishable by ``page`` in every column that moves.

    ``at`` is when the write arrives and ``observed`` when the reader was there;
    they are the same instant unless a test pulls them apart, which is how the
    two-tab race is written down.
    """
    return WebReadingPosition.create(
        user_id=reader,
        book_id=BookId(book.id),
        locator={"href": "OEBPS/chapter1.xhtml", "type": "x", "locations": {"position": page}},
        xpoint=XPoint.parse(f"/body/DocFragment[{page}]/body/div[1]/p[1]"),
        locator_source_hash=f"hash-of-page-{page}",
        written_at=at,
        recorded_at=observed or at,
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


async def stored_for(
    positions: WebReadingPositionRepository, book: Book, reader: UserId = READER
) -> WebReadingPosition:
    found = await positions.find_for_book(BookId(book.id), reader)
    assert found is not None
    return found


def assert_is_page(position: WebReadingPosition, page: int) -> None:
    assert position.position == Position(index=page, char_index=0)
    assert position.locator["locations"] == {"position": page}
    assert position.xpoint == XPoint.parse(f"/body/DocFragment[{page}]/body/div[1]/p[1]")
    assert position.locator_source_hash == f"hash-of-page-{page}"


class TestRecordingAPosition:
    """One row per reader and book, however many writers there are."""

    async def test_the_first_write_creates_the_row(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        recorded = await positions.record(a_position(book, FIRST))

        assert recorded is not None
        assert recorded.position.reading_session_id is None
        assert recorded.advanced is True
        assert await row_count(db_session) == 1
        assert_is_page(await stored_for(positions, book), 1)

    async def test_a_second_first_write_updates_rather_than_collides(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        """Two tabs opened together both find nothing stored and both go on to write.

        As a plain insert the second was a unique-constraint violation -- a 500
        for the reader, and a reading session with nothing left pointing at it.
        """
        await positions.record(a_position(book, FIRST))

        second = await positions.record(a_position(book, FIRST + timedelta(seconds=1), page=2))

        assert second is not None
        assert_is_page(second.position, 2)
        assert await row_count(db_session) == 1

    async def test_a_write_that_is_not_later_than_the_stored_one_changes_nothing(
        self, positions: WebReadingPositionRepository, book: Book
    ) -> None:
        """``None`` rather than an exception: the caller answers with what is stored.

        What matters is that it hears it *before* writing a reading session,
        which is why this is the first write the endpoint makes.
        """
        await positions.record(a_position(book, FIRST, page=9))

        overtaken = await positions.record(
            a_position(book, FIRST, page=1, observed=FIRST + timedelta(hours=1))
        )

        assert overtaken is None
        assert_is_page(await stored_for(positions, book), 9)

    async def test_the_row_reports_the_session_that_was_open_before_it(
        self,
        positions: WebReadingPositionRepository,
        book: Book,
        db_session: AsyncSession,
        recorded: WebReadingPosition,
    ) -> None:
        opened = await a_session(db_session, book, "open")
        await positions.attach_session(recorded, opened)

        later = await positions.record(a_position(book, FIRST + timedelta(minutes=1), page=2))

        assert later is not None
        assert later.position.reading_session_id == opened

    async def test_another_readers_place_in_the_same_book_is_untouched(
        self, positions: WebReadingPositionRepository, book: Book, db_session: AsyncSession
    ) -> None:
        db_session.add(User(id=OTHER_READER.value, email="other@test.com"))
        await db_session.commit()
        await positions.record(a_position(book, FIRST, page=9, reader=OTHER_READER))

        await positions.record(a_position(book, FIRST + timedelta(minutes=1), page=1))

        assert_is_page(await stored_for(positions, book, OTHER_READER), 9)
        assert_is_page(await stored_for(positions, book), 1)
        assert await row_count(db_session) == 2


class TestWhetherAWriteMovesThePosition:
    """Arrival says whether a write lands; the reader's clock says whether it moves."""

    async def test_a_write_carrying_an_older_sighting_lands_without_moving_anything(
        self, positions: WebReadingPositionRepository, book: Book
    ) -> None:
        """A tab idling on page 1 is closed while another has read on to page 9.

        Its write arrives last carrying an hour-old sighting. It has to land --
        it is closing a sitting -- and it must not put page 1 back.
        """
        await positions.record(a_position(book, FIRST + timedelta(hours=1), page=9))

        arrival = FIRST + timedelta(hours=2)
        stale = await positions.record(a_position(book, arrival, page=1, observed=FIRST))

        assert stale is not None, "the write must land: it has a session to close"
        assert stale.advanced is False
        assert stale.position.updated_at == arrival
        assert_is_page(stale.position, 9)
        assert_is_page(await stored_for(positions, book), 9)

    async def test_a_newer_sighting_moves_the_position(
        self, positions: WebReadingPositionRepository, book: Book
    ) -> None:
        """Paired with the test above: a rule that never moved anything would pass that."""
        await positions.record(a_position(book, FIRST, page=1))

        moved = await positions.record(a_position(book, FIRST + timedelta(minutes=1), page=9))

        assert moved is not None
        assert moved.advanced is True
        assert_is_page(moved.position, 9)
        assert_is_page(await stored_for(positions, book), 9)

    async def test_a_sighting_tied_with_the_stored_one_moves_the_position(
        self, positions: WebReadingPositionRepository, book: Book
    ) -> None:
        """A tie carries no information on the reader's clock, so arrival decides.

        Whichever way it is settled, what is stored and what ``advanced`` reports
        have to agree -- a rule that let them disagree kept page 1 while telling
        the caller it had moved.
        """
        await positions.record(a_position(book, FIRST, page=1))

        tied = await positions.record(
            a_position(book, FIRST + timedelta(minutes=1), page=7, observed=FIRST)
        )

        assert tied is not None
        assert tied.advanced is True
        assert_is_page(await stored_for(positions, book), 7)


class TestClaimingTheSessionPointer:
    """Only the writer that is still the latest may move the open-session pointer."""

    async def test_the_latest_writer_may_point_the_row_at_its_session(
        self,
        positions: WebReadingPositionRepository,
        book: Book,
        db_session: AsyncSession,
        recorded: WebReadingPosition,
    ) -> None:
        mine = await a_session(db_session, book, "mine")

        await positions.attach_session(recorded, mine)

        assert (await stored_for(positions, book)).reading_session_id == mine

    async def test_the_latest_writer_may_close_the_sitting(
        self,
        positions: WebReadingPositionRepository,
        book: Book,
        db_session: AsyncSession,
        recorded: WebReadingPosition,
    ) -> None:
        mine = await a_session(db_session, book, "mine")
        await positions.attach_session(recorded, mine)

        await positions.attach_session(recorded, None)

        assert (await stored_for(positions, book)).reading_session_id is None

    async def test_an_overtaken_writer_may_not(
        self,
        positions: WebReadingPositionRepository,
        book: Book,
        db_session: AsyncSession,
        recorded: WebReadingPosition,
    ) -> None:
        """What stops a close undoing a page turn that arrived after it, and the reverse."""
        winner = await a_session(db_session, book, "winner")
        loser = await a_session(db_session, book, "loser")
        later = await positions.record(a_position(book, FIRST + timedelta(minutes=1), page=2))
        assert later is not None
        await positions.attach_session(later.position, winner)

        await positions.attach_session(recorded, loser)

        assert (await stored_for(positions, book)).reading_session_id == winner

    async def test_deleting_the_session_leaves_the_reader_their_place(
        self,
        positions: WebReadingPositionRepository,
        book: Book,
        db_session: AsyncSession,
        recorded: WebReadingPosition,
    ) -> None:
        """SET NULL, not CASCADE: no open session is a fresh one, not a lost place."""
        opened = await a_session(db_session, book, "open")
        await positions.attach_session(recorded, opened)

        await db_session.execute(
            delete(ReadingSessionORM).where(ReadingSessionORM.id == opened.value)
        )
        await db_session.commit()

        stored = await stored_for(positions, book)
        assert stored.reading_session_id is None
        assert_is_page(stored, 1)
