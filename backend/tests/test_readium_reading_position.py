"""Reading position and reading sessions from the browser (M2.3, #742; M2.4, #743).

Three things are under test here and they are not the same thing.

The **position** is what the browser stores so it can be put back where it was:
a Readium locator, converted on the way in to the KOReader xpointer that both
readers agree on (ADR-0004 §2) and refused if the conversion cannot say where it
is (§5).

The **session** is what everything *else* in Crossbill reads. Reading progress
and the statistics page are computed from ``reading_sessions`` and know nothing
about the web reader, so the way browser reading reaches them is by being
ordinary rows in that table (ADR-0004, Amendment 3). The assertions below are
therefore made through ``/statistics`` wherever they can be: what matters is not
that a row exists but that the page a reader looks at counts it.

The **resume** is where the browser opens the book, which is neither of the
above and is answered by the same ``GET``. It is the later of the two sightings
the reader has -- their stored web position, or the end of a sitting an e-reader
synced -- and the second of those has only ever been an xpointer, so a locator
is derived from the EPUB on the way out (``TestResumingWhereAnyDeviceLeftOff``).

Every locator here is built from ``tests/fixtures/minimal.epub`` and converted
for real -- no anchor service is faked, because the confidence a quote comes
back with is the thing being relied on. The fixture is built for it: chapter one
repeats one sentence in two paragraphs, so quoting that sentence alone is
genuinely ambiguous and quoting it with what precedes it is not.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.web_reader.queries.publication_positions import (
    MAX_PUBLICATION_POSITIONS,
)
from src.domain.common.time import as_aware
from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.reading.routers.reader_clock import reader_now
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
)
from src.main import app
from src.models import Book, ReadingSession, User
from tests.conftest import create_test_book, create_test_reading_session, readers_today
from tests.test_readium_manifest import fixture_bytes, store_epub
from tests.test_readium_session import present, start_publication_session

CHAPTER_ONE = "resources/OEBPS/chapter1.xhtml"
CHAPTER_TWO = "resources/OEBPS/chapter2.xhtml"
XHTML = "application/xhtml+xml"

# The last paragraph of chapter one: it occurs once, so its quote alone says
# where it is. Position 10 of 18 in the fixture's document order.
LAST_PARAGRAPH = "Nothing else in the house moved until morning."
LAST_PARAGRAPH_SELECTOR = "#intro > p:nth-child(5)"
LAST_PARAGRAPH_XPOINT = "/body/DocFragment[1]/body/div[1]/p[4]"
LAST_PARAGRAPH_POSITION = {"index": 10, "char_index": 0}

# The first paragraph of chapter two. Position 16 of 18 -- further on, so a
# progress percentage built from it differs from the one above.
SECOND_CHAPTER = "Morning arrived without ceremony."
SECOND_CHAPTER_SELECTOR = "#second > p:nth-child(2)"
SECOND_CHAPTER_POSITION = {"index": 16, "char_index": 0}

# The sentence chapter one uses twice. Sent with no CSS selector it names two
# places and nothing settles which; with the heading before it, exactly one.
REPEATED = "The lantern went out at midnight."
FIRST_PARAGRAPH_CONTEXT = "Chapter One"
FIRST_PARAGRAPH_XPOINT = "/body/DocFragment[1]/body/div[1]/p[1]"

# The same repeated sentence, disambiguated onto its *second* paragraph, which
# sits between the two above in document order. Three known places one element
# apart is what lets a backward move be made small on purpose.
THIRD_PARAGRAPH_CONTEXT = "She wrote the same sentence twice, and meant it both times."

# Where each quote is, and the CSS selector a navigator would have sent with it,
# so that a test names a paragraph once and every write of it is shaped like the
# real thing. A quote absent from here is written against chapter one with no
# selector at all, which is how the ambiguous cases below are made ambiguous.
PLACE_OF = {
    LAST_PARAGRAPH: (CHAPTER_ONE, LAST_PARAGRAPH_SELECTOR),
    SECOND_CHAPTER: (CHAPTER_TWO, SECOND_CHAPTER_SELECTOR),
}


# What the resume endpoint answers for a book nobody has read on any device.
# Spelled out whole rather than asserted field by field, because the difference
# between this and a *lost* position is one field, and a test that only looked
# at `locator` would not see it.
NOWHERE_TO_RESUME = {
    "locator": None,
    "source": None,
    "unresolved": False,
    "xpoint": None,
    "position": None,
    "recorded_at": None,
}

# Where an e-reader might have left off: the first paragraph of chapter two, one
# element on from where `SECOND_CHAPTER` quotes. KOReader stores an xpointer and
# nothing else, so this is the whole of what a synced session says about where
# the reader is.
KOREADER_XPOINT = "/body/DocFragment[2]/body/div[1]/p[1]"
KOREADER_DEVICE = "kobo-clara"

# An xpointer into a fifth spine document, which `minimal.epub` does not have.
# The shape a replaced EPUB takes: the position is still safely stored, and
# there is no longer anywhere in this book to put it.
XPOINT_IN_ANOTHER_EDITION = "/body/DocFragment[5]/body/div[1]/p[3]"


def position_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/reading-position"


def a_page_turn(
    href: str = CHAPTER_ONE, progression: float = 0.0, position: int = 1
) -> dict[str, Any]:
    """A locator exactly as a page turn produces one -- which is to say, textless.

    This is the shape production sends and the shape that broke: ``EpubNavigator``
    reports a turn from its column snapper's ``progress`` event, and the Locator
    it builds carries an href, a position, a progression, an empty ``fragments``
    list, and no text at all. Copied from one captured in the reader's own
    browser test rather than imagined, because every fixture below that carries
    a quote is a shape the navigator only rarely produces.
    """
    return {
        "href": href,
        "type": XHTML,
        "locations": {
            "fragments": [],
            "progression": progression,
            "totalProgression": progression / 2,
            "position": position,
        },
    }


def locator(
    quote: str, before: str | None = None, progression: float = 0.5, page: int | None = None
) -> dict[str, Any]:
    """A locator shaped the way ``@readium/navigator`` serializes one.

    The href is the manifest's -- the URL this API serves the file from -- and
    not the path inside the EPUB container, because that is what a navigator has
    ever been told the resource is called.

    The selector is load-bearing rather than decoration: it narrows the search
    for the quote to one element, which is usually what makes a repeated
    sentence unambiguous in real reading. A quote with none registered in
    :data:`PLACE_OF` is sent without one, which is how a locator with nothing
    but a quote to go on is written here.
    """
    href, selector = PLACE_OF.get(quote, (CHAPTER_ONE, None))
    text: dict[str, Any] = {"highlight": quote}
    if before is not None:
        text["before"] = before
    locations: dict[str, Any] = {"progression": progression}
    if page is not None:
        locations["position"] = page
    if selector is not None:
        locations["cssSelector"] = selector
    return {"href": href, "type": XHTML, "locations": locations, "text": text}


async def put_position(
    client: AsyncClient,
    book_id: int,
    quote: str,
    at: datetime,
    before: str | None = None,
    closing: bool = False,
    arriving: datetime | None = None,
    page: int | None = None,
) -> Response:
    """Write a position the way the reader does: a locator and the moment it was seen."""
    return await put_locator(
        client, book_id, locator(quote, before=before, page=page), at, closing, arriving
    )


async def put_locator(
    client: AsyncClient,
    book_id: int,
    body: dict[str, Any],
    at: datetime,
    closing: bool = False,
    arriving: datetime | None = None,
) -> Response:
    """Write one locator, whatever shape it is in.

    ``at`` is the reader's clock and ``arriving`` is the server's, which decides
    which of two writes is the later. They are the same instant unless a test
    says otherwise, because in life they very nearly are -- and a test that
    pulls them apart is testing exactly that.
    """
    with server_clock(arriving or at):
        return await client.put(
            position_url(book_id),
            json={"locator": body, "recorded_at": at.isoformat(), "closing": closing},
        )


@contextmanager
def server_clock(at: datetime) -> Iterator[None]:
    """Pin what the server thinks the time is, for one request.

    Written down rather than left to the real clock because a reading session's
    arithmetic is in minutes and a test's is in microseconds: without this,
    every write below would land in the same instant and no session could span
    anything.
    """
    app.dependency_overrides[reader_now] = lambda: at
    try:
        yield
    finally:
        del app.dependency_overrides[reader_now]


@pytest.fixture
async def readable_book(db_session: AsyncSession, test_book: Book, storage_dir: Path) -> Book:
    """The user's own book, with an EPUB behind it that really parses."""
    await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))
    return test_book


async def sessions_for(db_session: AsyncSession, book: Book) -> list[ReadingSession]:
    """Every reading session recorded for the book, oldest first."""
    rows = await db_session.execute(
        select(ReadingSession)
        .where(ReadingSession.book_id == book.id)
        .order_by(ReadingSession.start_time)
    )
    return list(rows.scalars().unique().all())


class TestStoringAPosition:
    """What a write stores, and what a read gives back."""

    async def test_a_written_position_comes_back(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should convert the locator, place it in the book, and round-trip the lot."""
        moment = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)

        written = await put_position(client, readable_book.id, LAST_PARAGRAPH, moment)

        assert written.status_code == status.HTTP_200_OK, written.text
        body = written.json()
        assert body["xpoint"] == LAST_PARAGRAPH_XPOINT
        assert body["position"] == LAST_PARAGRAPH_POSITION
        assert body["locator"]["text"]["highlight"] == LAST_PARAGRAPH

        read_back = await client.get(position_url(readable_book.id))

        assert read_back.status_code == status.HTTP_200_OK
        stored = read_back.json()
        assert stored["xpoint"] == LAST_PARAGRAPH_XPOINT
        assert stored["position"] == LAST_PARAGRAPH_POSITION
        # The locator is handed back whole, including the parts only a navigator
        # understands: this is what M2.4 navigates to, so anything dropped here
        # is a reader who resumes somewhere vaguer than where they left off.
        assert stored["locator"]["href"] == CHAPTER_ONE
        assert stored["locator"]["locations"]["cssSelector"] == LAST_PARAGRAPH_SELECTOR
        assert stored["locator"]["locations"]["progression"] == 0.5

    async def test_a_book_never_read_anywhere_has_no_position(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should answer an empty resume rather than 404: an unread book is not a missing one.

        And not ``unresolved`` either: nothing was lost, there was simply never
        anywhere to go back to, which is what the reader must not be told about.
        """
        response = await client.get(position_url(readable_book.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == NOWHERE_TO_RESUME

    async def test_a_later_write_replaces_an_earlier_one(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should move the stored position as the reader moves."""
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, start)

        await put_position(client, readable_book.id, SECOND_CHAPTER, start + timedelta(minutes=2))

        stored = (await client.get(position_url(readable_book.id))).json()
        assert stored["position"] == SECOND_CHAPTER_POSITION

    async def test_a_slow_clock_still_records_its_reading(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should let a write land on arrival, whatever the reader's clock claims.

        Whether a write happens at all is a fact about this server. A second
        device whose clock is five minutes slow would otherwise have every write
        it ever made read as older than what is stored and be refused for good.
        Its reading is counted; only the *position* waits for its clock to catch
        up, which the test below is about.
        """
        first = datetime(2026, 3, 1, 9, 10, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, first)

        slow = await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            arriving=datetime(2026, 3, 1, 9, 11, tzinfo=UTC),
        )

        assert slow.status_code == status.HTTP_200_OK, slow.text
        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 1
        assert sessions[0].end_time - sessions[0].start_time == timedelta(minutes=1)

    async def test_an_idle_tab_closing_does_not_drag_the_reader_backwards(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should keep the page a live tab reached when a stale one closes on an old page.

        Two tabs, one book. The first sits on its page while the second reads
        on; then the first is closed, and its dying write arrives *last* --
        carrying a position its reader left long ago. Ordering on arrival alone,
        that write wins: the stored position falls back to the abandoned page,
        and a resume would put the reader there.

        So arrival decides only whether a write happens. Whether it *moves* the
        position is settled on the reader's own clock, which is what the closing
        write cannot forge -- it is honestly carrying an old observation. It
        still closes the sitting, which is what it came to say.
        """
        idling_at = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, idling_at)
        await put_position(
            client, readable_book.id, SECOND_CHAPTER, datetime(2026, 3, 1, 9, 20, tzinfo=UTC)
        )

        closing = await put_position(
            client,
            readable_book.id,
            LAST_PARAGRAPH,
            idling_at,
            closing=True,
            arriving=datetime(2026, 3, 1, 9, 21, tzinfo=UTC),
        )

        assert closing.status_code == status.HTTP_200_OK, closing.text
        assert closing.json()["position"] == SECOND_CHAPTER_POSITION
        stored = (await client.get(position_url(readable_book.id))).json()
        assert stored["position"] == SECOND_CHAPTER_POSITION
        # The sitting was not dragged back either: progress is where the live
        # tab got to, not where the closed one had been sitting.
        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 1
        assert sessions[0].end_position == [16, 0]

    async def test_a_stale_write_that_finds_no_sitting_open_invents_none(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should record nothing when a tab closes on a page nothing is reading any more.

        The write moved no position and found no sitting to extend, so there is
        nothing it could honestly be a session of.
        """
        await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            datetime(2026, 3, 1, 9, 20, tzinfo=UTC),
            closing=True,
        )
        before = len(await sessions_for(db_session, readable_book))

        await put_position(
            client,
            readable_book.id,
            LAST_PARAGRAPH,
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            closing=True,
            arriving=datetime(2026, 3, 1, 9, 21, tzinfo=UTC),
        )

        assert len(await sessions_for(db_session, readable_book)) == before

    async def test_a_write_overtaken_before_it_lands_changes_nothing(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should answer an overtaken write with what is stored, rather than refusing it.

        The write a closing tab sends and the one a page turn sends race by
        design, so the loser has to be harmless: no error for the page to
        handle, no rewinding of the position that won, and -- the part that used
        to be wrong -- no reading session left behind by a write that did not
        happen. The position is claimed before any session is touched precisely
        so that a loser has nothing to clean up.
        """
        await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            datetime(2026, 3, 1, 9, 5, tzinfo=UTC),
        )

        overtaken = await put_position(
            client,
            readable_book.id,
            LAST_PARAGRAPH,
            datetime(2026, 3, 1, 9, 4, tzinfo=UTC),
            arriving=datetime(2026, 3, 1, 9, 4, tzinfo=UTC),
        )

        assert overtaken.status_code == status.HTTP_200_OK
        assert overtaken.json()["position"] == SECOND_CHAPTER_POSITION
        assert len(await sessions_for(db_session, readable_book)) == 1

    async def test_a_clock_that_runs_ahead_cannot_claim_the_future(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should not credit a reader with reading time their clock invented.

        Asserted on the session rather than the stored position, because the
        session is where a claimed moment turns into a duration somebody is
        credited with.
        """
        arriving = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)

        response = await put_position(
            client,
            readable_book.id,
            LAST_PARAGRAPH,
            arriving + timedelta(days=7),
            arriving=arriving,
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        sessions = await sessions_for(db_session, readable_book)
        assert as_aware(sessions[0].end_time) == arriving

    async def test_a_wild_clock_cannot_invent_reading_time(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should measure a sitting on the server's clock alone, however it is addressed.

        The reader's clock says where they were, never how long they read. A
        write claiming a year ago and one claiming next week both land at the
        moment they arrive, so a session is exactly as long as the server
        watched it run -- which is a stronger guarantee than any bound on what
        a client may claim, and needs no bound at all.
        """
        arriving = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(
            client,
            readable_book.id,
            LAST_PARAGRAPH,
            arriving - timedelta(days=365),
            arriving=arriving,
        )

        await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            arriving + timedelta(days=7),
            arriving=arriving + timedelta(minutes=5),
        )

        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 1
        assert as_aware(sessions[0].start_time) == arriving
        assert sessions[0].end_time - sessions[0].start_time == timedelta(minutes=5)


class TestThePositionAPageTurnActuallySends:
    """The textless locator a reflowable page turn produces -- the primary path.

    Everything in :class:`TestStoringAPosition` hands the server a quote, which
    is what a *selection* produces. A page turn produces none, and for a while
    that meant every real write in production was refused 422 while every test
    here passed. These are the tests that would have caught it.
    """

    async def test_a_page_turn_is_stored(self, client: AsyncClient, readable_book: Book) -> None:
        """Should place a locator that carries nothing but an href and a progression."""
        response = await put_locator(
            client,
            readable_book.id,
            a_page_turn(href=CHAPTER_TWO, progression=0.0),
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        # Chapter two's first element, which is where progression 0 of it is.
        assert body["xpoint"].startswith("/body/DocFragment[2]/")
        assert body["position"] is not None

    async def test_progression_lands_where_it_points(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should put a reader most of the way through a chapter further on than one at its start.

        The exact element is not the assertion -- a fraction of a resource's
        characters is not a fraction of its rendered pages, and this never
        claimed otherwise. That the two differ, in the right direction, is.
        """
        start = await put_locator(
            client,
            readable_book.id,
            a_page_turn(progression=0.0),
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )
        later = await put_locator(
            client,
            readable_book.id,
            a_page_turn(progression=0.9),
            datetime(2026, 3, 1, 9, 5, tzinfo=UTC),
        )

        assert start.status_code == status.HTTP_200_OK, start.text
        assert later.status_code == status.HTTP_200_OK, later.text
        assert later.json()["position"]["index"] > start.json()["position"]["index"]

    async def test_the_end_of_a_resource_is_still_a_place(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should place a reader at the very end of a chapter, where no text follows.

        A caret is expressed as the text after it, and at progression 1 there is
        none -- so the anchor has to fall back to the text before it or the last
        page of every chapter would be unrecordable.
        """
        response = await put_locator(
            client,
            readable_book.id,
            a_page_turn(progression=1.0),
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["position"] is not None

    async def test_an_element_named_by_selector_beats_a_progression(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should use the element a locator names, not the fraction beside it.

        The progression here points at the start of the chapter and the selector
        at its last paragraph; the selector is the one that knows.
        """
        page_turn = a_page_turn(progression=0.0)
        page_turn["locations"]["cssSelector"] = LAST_PARAGRAPH_SELECTOR

        response = await put_locator(
            client, readable_book.id, page_turn, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["xpoint"] == LAST_PARAGRAPH_XPOINT

    async def test_a_fragment_id_names_an_element_too(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should follow a fragment identifier, which a reader gets by following a link."""
        page_turn = a_page_turn(href=CHAPTER_TWO, progression=0.9)
        page_turn["locations"]["fragments"] = ["#second"]

        response = await put_locator(
            client, readable_book.id, page_turn, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        # `#second` wraps chapter two from its heading, so the anchor is the heading.
        assert response.json()["xpoint"] == "/body/DocFragment[2]/body/div[1]/h1[1]"

    async def test_a_locator_naming_no_resource_is_still_refused(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should refuse a page turn in a chapter this book does not have.

        The fallbacks are about reading a position from thin evidence, not about
        accepting anything: a locator naming a resource the book has not got is
        an EPUB that has been replaced, which is what ADR-0004 §5 is for.
        """
        response = await put_locator(
            client,
            readable_book.id,
            a_page_turn(href="resources/OEBPS/chapter99.xhtml"),
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text

    @pytest.mark.parametrize(
        "position",
        [2**63, MAX_PUBLICATION_POSITIONS + 1, 2_000_000_000, -1],
        ids=["overflows-the-column", "past-the-longest-publication", "billions", "negative"],
    )
    async def test_a_page_number_no_position_list_could_hold_is_refused(
        self, client: AsyncClient, readable_book: Book, position: int
    ) -> None:
        """Should refuse a synthetic page number outside what this API could have served.

        ``locations.position`` is only ever a number the browser read out of a
        position list of ours, so one that no publication could produce is not a
        position at all. Unbounded it was two failures at once: a value past the
        column's range killed the request with a 500, and a merely enormous one
        was written down and credited as billions of pages read.
        """
        page_turn = a_page_turn()
        page_turn["locations"]["position"] = position

        response = await put_locator(
            client, readable_book.id, page_turn, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text

    @pytest.mark.parametrize(
        "progression", ["NaN", "Infinity", "-Infinity", "1e308", "-0.5", "2.0"], ids=str
    )
    async def test_a_progression_that_is_not_a_fraction_is_refused(
        self, client: AsyncClient, readable_book: Book, progression: str
    ) -> None:
        """Should refuse a progression outside 0..1 rather than compute with it.

        JSON has no NaN literal but Python's parser reads one anyway, and a
        progression is multiplied by a length and rounded -- so ``NaN`` raised
        a ValueError and ``Infinity`` an OverflowError, both of them 500s, from
        a body a client can simply send.
        """
        body = (
            f'{{"locator": {{"href": "{CHAPTER_ONE}", "type": "{XHTML}", '
            f'"locations": {{"progression": {progression}}}}}, '
            f'"recorded_at": "2026-03-01T09:00:00+00:00", "closing": false}}'
        )

        with server_clock(datetime(2026, 3, 1, 9, 0, tzinfo=UTC)):
            response = await client.put(
                position_url(readable_book.id),
                content=body,
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text

    async def test_a_locator_with_nothing_to_go_on_is_refused(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should refuse a locator carrying no text, no element and no progression."""
        response = await put_locator(
            client,
            readable_book.id,
            {"href": CHAPTER_ONE, "type": XHTML, "locations": {}},
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text


class TestRefusingAPosition:
    """Positions the server cannot place, and will not guess at."""

    async def test_an_ambiguous_quote_is_refused(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should refuse a quote the book uses twice with nothing to tell them apart.

        Not an error the reader caused -- the request is perfectly well formed --
        so 422 rather than 400, and nothing is stored.
        """
        response = await put_position(
            client, readable_book.id, REPEATED, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
        assert response.json()["error"] == "unresolvable_position"
        assert (await client.get(position_url(readable_book.id))).json() == NOWHERE_TO_RESUME

    async def test_the_same_quote_is_accepted_once_context_settles_it(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should store the very quote refused above when the text before it names one place.

        The pair is the point: what is rejected is the *weakness of the match*,
        not the sentence, so a floor that simply refused everything would pass
        the test above and fail this one.
        """
        response = await put_position(
            client,
            readable_book.id,
            REPEATED,
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            before=FIRST_PARAGRAPH_CONTEXT,
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["xpoint"] == FIRST_PARAGRAPH_XPOINT

    async def test_a_quote_that_is_not_in_the_book_is_refused(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should refuse text the EPUB does not contain, rather than guess a nearby place."""
        response = await put_position(
            client,
            readable_book.id,
            "This sentence is in no edition of this book.",
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text

    async def test_a_book_with_no_epub_has_nowhere_to_put_a_position(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        """Should answer 404 for a book there is nothing to read, as the reader routes do."""
        assert test_book.ebook_file is None

        response = await put_position(
            client, test_book.id, LAST_PARAGRAPH, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestWhoMayReadAndWrite:
    """The access rules, at both doors."""

    async def test_reading_requires_authentication(
        self, anonymous_client: AsyncClient, readable_book: Book
    ) -> None:
        """Should refuse an unauthenticated read of where somebody got to."""
        response = await anonymous_client.get(position_url(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_writing_requires_authentication(
        self, anonymous_client: AsyncClient, readable_book: Book
    ) -> None:
        """Should refuse an unauthenticated write."""
        response = await put_position(
            anonymous_client,
            readable_book.id,
            LAST_PARAGRAPH,
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_another_users_book_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        storage_dir: Path,
    ) -> None:
        """Should answer 404 at both doors for a readable book that is not the caller's."""
        theirs = await create_test_book(
            db_session=db_session, user_id=other_user.id, title="Not Yours"
        )
        await store_epub(
            db_session, theirs, storage_dir, fixture_bytes("minimal.epub"), "theirs.epub"
        )

        read = await client.get(position_url(theirs.id))
        write = await put_position(
            client, theirs.id, LAST_PARAGRAPH, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )

        assert read.status_code == status.HTTP_404_NOT_FOUND
        assert write.status_code == status.HTTP_404_NOT_FOUND
        assert await sessions_for(db_session, theirs) == []

    async def test_the_publication_cookie_opens_both(
        self,
        browser_client: AsyncClient,
        test_user: User,
        readable_book: Book,
    ) -> None:
        """Should serve a request carrying only the cookie an iframe would have.

        These two routes are under the publication cookie's path scope on
        purpose: the reader writes positions from a page whose other credential
        may have lapsed, and one credential rule for the whole web reader is
        what keeps that a single thing to get wrong.
        """
        minted = await start_publication_session(browser_client, test_user, readable_book.id)
        assert minted.status_code == status.HTTP_200_OK, minted.text

        written = await put_position(
            browser_client, readable_book.id, LAST_PARAGRAPH, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )
        read = await browser_client.get(position_url(readable_book.id))

        assert written.status_code == status.HTTP_200_OK, written.text
        assert read.status_code == status.HTTP_200_OK
        assert read.json()["xpoint"] == LAST_PARAGRAPH_XPOINT

    async def test_the_cookie_opens_no_other_book(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        readable_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should refuse book A's cookie at book B's position, both books being the caller's."""
        other = await create_test_book(
            db_session=db_session, user_id=test_user.id, title="Also Mine", client_book_id="other"
        )
        await store_epub(
            db_session, other, storage_dir, fixture_bytes("minimal.epub"), "other.epub"
        )
        minted = await start_publication_session(browser_client, test_user, readable_book.id)
        present(browser_client, minted.cookies[PUBLICATION_COOKIE_NAME])

        read = await browser_client.get(position_url(other.id))
        write = await put_position(
            browser_client, other.id, LAST_PARAGRAPH, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )

        assert read.status_code == status.HTTP_401_UNAUTHORIZED, read.text
        assert write.status_code == status.HTTP_401_UNAUTHORIZED, write.text

    async def test_a_bearer_token_still_opens_both(
        self, browser_client: AsyncClient, test_user: User, readable_book: Book
    ) -> None:
        """Should keep serving a plain Bearer request, which is how the SPA writes."""
        headers = {"Authorization": f"Bearer {create_access_token(test_user.id)}"}

        response = await browser_client.get(position_url(readable_book.id), headers=headers)

        assert response.status_code == status.HTTP_200_OK, response.text


class TestTheReadingSessionsThisMakes:
    """Browser reading, as the rest of Crossbill sees it."""

    async def test_a_sitting_is_one_session(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should gather several page turns into one session spanning first write to last.

        Not three sessions of no duration, which is what writing a row per
        position would produce.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, start)
        await put_position(
            client,
            readable_book.id,
            REPEATED,
            start + timedelta(minutes=4),
            before=FIRST_PARAGRAPH_CONTEXT,
        )
        await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            start + timedelta(minutes=11),
        )

        sessions = await sessions_for(db_session, readable_book)

        assert len(sessions) == 1
        assert sessions[0].start_xpoint == LAST_PARAGRAPH_XPOINT
        assert sessions[0].end_position == [16, 0]
        assert sessions[0].device_id == "crossbill-web-reader"
        span = sessions[0].end_time - sessions[0].start_time
        assert span == timedelta(minutes=11)

    async def test_writing_the_same_place_again_keeps_the_session_alive(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should extend a session from a write that repeats the position it already has.

        This is what the reader's heartbeat rests on. Someone on one page for
        twenty minutes turns nothing and so reports nothing, and their session
        would end at their first page turn and never mention the twenty minutes;
        so the reader re-sends where it is while the tab is open. A server that
        treated an unchanged position as nothing to do would make that pointless.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, start)

        await put_position(client, readable_book.id, LAST_PARAGRAPH, start + timedelta(minutes=9))

        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 1
        assert sessions[0].end_time - sessions[0].start_time == timedelta(minutes=9)

    async def test_a_long_gap_starts_a_new_session(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should cut a session when nothing has been heard for longer than the timeout.

        Both writes are the same reader in the same book; only the hour between
        them makes two sittings out of one.
        """
        morning = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, morning)

        await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            morning + timedelta(hours=1),
        )

        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 2
        assert sessions[1].start_time - sessions[0].start_time == timedelta(hours=1)

    async def test_closing_the_book_ends_the_session(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should start a fresh session after a close, however soon the reader returns.

        The write that closes still counts: it carries the last position the
        reader reached, which is what a session is for.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, start)
        await put_position(
            client,
            readable_book.id,
            REPEATED,
            start + timedelta(minutes=3),
            before=FIRST_PARAGRAPH_CONTEXT,
            closing=True,
        )

        await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            start + timedelta(minutes=4),
        )

        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 2
        assert sessions[0].end_time - sessions[0].start_time == timedelta(minutes=3)
        assert sessions[1].end_position == [16, 0]

    async def test_a_session_carries_the_page_range_the_reader_was_shown(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should record the pages a sitting covered, as the sessions list renders them.

        A session's pages are the numbers the reader themselves watched go by
        -- ``locations.position`` is the Readium position list this API served,
        and it is what the reader's chrome says "Page X of N" from. Left null,
        a browser session rendered without its page range while every synced
        one had it, and a book read on both demoted its whole activity grid
        from pages to minutes.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_locator(client, readable_book.id, a_page_turn(progression=0.0), start)
        await put_locator(
            client,
            readable_book.id,
            a_page_turn(href=CHAPTER_TWO, progression=0.5, position=4),
            start + timedelta(minutes=6),
        )

        listed = await client.get(f"/api/v1/books/{readable_book.id}/reading_sessions")

        assert listed.status_code == status.HTTP_200_OK, listed.text
        [session] = listed.json()["items"]
        assert session["start_page"] == 1
        assert session["end_page"] == 4

    async def test_a_sitting_that_never_turns_a_page_still_has_one(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should show the one page a reader stayed on, rather than no pages at all.

        The heartbeat writes the same position again to say the reader is still
        there, so a sitting can genuinely span one page from beginning to end.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_locator(client, readable_book.id, a_page_turn(position=2), start)
        await put_locator(
            client, readable_book.id, a_page_turn(position=2), start + timedelta(minutes=9)
        )

        listed = await client.get(f"/api/v1/books/{readable_book.id}/reading_sessions")

        [session] = listed.json()["items"]
        assert session["start_page"] == 2
        assert session["end_page"] == 2

    async def test_paging_back_a_little_keeps_the_pages_the_sitting_covered(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should stay one sitting when a reader turns back a page, keeping the furthest.

        The same rule the xpoint range follows, and for the same reason: a range
        that ran backwards would not be one, and what the card reports is the
        ground the sitting covered.

        The fixture is 18 elements, so a quarter of it is four and a half; this
        walks 6 → 10 → 9 in document order, a single element back, which is
        ordinary re-reading and well inside the threshold.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(
            client, readable_book.id, REPEATED, start, before=FIRST_PARAGRAPH_CONTEXT, page=2
        )
        await put_position(
            client, readable_book.id, LAST_PARAGRAPH, start + timedelta(minutes=2), page=4
        )
        await put_position(
            client,
            readable_book.id,
            REPEATED,
            start + timedelta(minutes=4),
            before=THIRD_PARAGRAPH_CONTEXT,
            page=3,
        )

        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 1
        assert (sessions[0].start_page, sessions[0].end_page) == (2, 4)
        # Progress follows the reader; the page range keeps the ground covered.
        assert sessions[0].end_position == [9, 0]

    async def test_starting_the_book_again_is_a_new_sitting(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should cut a new session when a reader jumps back across the book.

        Otherwise a reader who finishes and starts again half an hour later is
        one sitting that reports every page of the book as read while the
        progress bar says page one -- the furthest-page rule and ``end_position``
        pulling in opposite directions. A quarter of a book is not a sequence of
        page turns; it is a contents link, a bookmark, or starting over.

        Here that is 16 → 6 of eighteen elements: ten back, where four and a
        half is the line. The sitting it left keeps what it covered.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, SECOND_CHAPTER, start, page=9)

        await put_position(
            client,
            readable_book.id,
            REPEATED,
            start + timedelta(minutes=2),
            before=FIRST_PARAGRAPH_CONTEXT,
            page=1,
        )

        sessions = await sessions_for(db_session, readable_book)
        assert len(sessions) == 2
        assert (sessions[0].start_page, sessions[0].end_page) == (9, 9)
        assert (sessions[1].start_page, sessions[1].end_page) == (1, 1)
        assert sessions[1].end_position == [6, 0]

    async def test_browser_reading_does_not_demote_a_paged_book_to_minutes(
        self, client: AsyncClient, db_session: AsyncSession, readable_book: Book
    ) -> None:
        """Should leave the activity grid counting pages for a book synced with them.

        The grid counts pages only when *every* session of the book has them
        (``ActivityUnitRule.EVERY_SESSION_PAGED``), so one page-less web session
        used to silently rewrite a KOReader-read book's whole year from pages
        into minutes. That is the consequence of the missing page range that a
        reader would not connect to having opened the book in a browser.
        """
        synced = ReadingSession(
            user_id=1,
            book_id=readable_book.id,
            start_time=datetime(2026, 2, 28, 20, 0, tzinfo=UTC),
            end_time=datetime(2026, 2, 28, 21, 0, tzinfo=UTC),
            start_page=1,
            end_page=30,
            content_hash="synced-from-the-ereader",
            device_id="kindle",
        )
        db_session.add(synced)
        await db_session.commit()

        await put_locator(
            client,
            readable_book.id,
            a_page_turn(position=31),
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        )

        with readers_today(date(2026, 3, 1)):
            response = await client.get(f"/api/v1/books/{readable_book.id}/statistics")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["activity"]["unit"] == "pages"

    async def test_the_statistics_page_counts_browser_reading(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should show reading done in the browser wherever e-reader reading shows.

        This is the whole of Amendment 3 in one assertion: nothing in the
        statistics, the progress percentage or the activity grid was taught
        about the web reader, and all three answer for it because what the
        reader wrote is an ordinary reading session.
        """
        start = datetime.now(UTC) - timedelta(minutes=20)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, start)
        await put_position(
            client,
            readable_book.id,
            SECOND_CHAPTER,
            start + timedelta(minutes=15),
        )

        response = await client.get(f"/api/v1/books/{readable_book.id}/statistics")

        assert response.status_code == status.HTTP_200_OK, response.text
        statistics = response.json()
        assert statistics["session_count"] == 1
        assert statistics["total_reading_seconds"] == 15 * 60
        # 16 of the fixture's 18 elements, backfilled onto the book by the same
        # write, because a browser-only book has never been through the upload
        # path that used to be the only thing that measured a book's length.
        assert statistics["progress_percent"] == 89


async def resume_for(client: AsyncClient, book_id: int) -> dict[str, Any]:
    """Ask where the browser should open a book, and insist on being answered.

    Never 404 and never null, whatever the answer turns out to be -- so a test
    that only cares *where* need not restate that every time.
    """
    response = await client.get(position_url(book_id))
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


class TestResumingWhereAnyDeviceLeftOff:
    """Where the browser opens a book, when the browser is not the only reader (M2.4, #743).

    The endpoint under test is the same ``GET`` the tests above read positions
    back through, but the question it answers is a wider one. A reader who got
    through three chapters on their e-reader last night and then opens the book
    here has no stored web position at that place -- KOReader stores an xpointer
    and nothing else -- so the answer has to come out of ``reading_sessions``
    and be converted to a locator against the EPUB (ADR-0004 §2).

    What the assertions turn on is which of the two candidates wins and what the
    reader is told when neither can be placed.
    """

    async def a_koreader_session(
        self,
        db_session: AsyncSession,
        book: Book,
        user_id: int,
        ended: datetime,
        xpoint: str = KOREADER_XPOINT,
    ) -> None:
        """Record a sitting synced from an e-reader, ending where ``xpoint`` says.

        Both xpoint columns are filled because the pair is read back as one
        range and a session with only one of them has neither.
        """
        await create_test_reading_session(
            db_session=db_session,
            book=book,
            user_id=user_id,
            start_time=ended - timedelta(minutes=20),
            minutes=20,
            start_xpoint=FIRST_PARAGRAPH_XPOINT,
            end_xpoint=xpoint,
            device_id=KOREADER_DEVICE,
        )

    async def test_an_e_reader_read_more_recently_wins(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        readable_book: Book,
    ) -> None:
        """Should open where the e-reader left off, converted into a locator to navigate to.

        The conversion is the point: what was stored is an xpointer, and what a
        navigator can be handed is a Locator naming a resource this API serves.
        """
        await put_position(
            client, readable_book.id, LAST_PARAGRAPH, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )
        await self.a_koreader_session(
            db_session, readable_book, test_user.id, datetime(2026, 3, 2, 21, 0, tzinfo=UTC)
        )

        resume = await resume_for(client, readable_book.id)
        assert resume["source"] == "koreader"
        assert resume["unresolved"] is False
        assert resume["xpoint"] == KOREADER_XPOINT
        # The href is the URL this API serves the file from, not the path inside
        # the EPUB container: the navigator has never been told the file is
        # called anything else.
        assert resume["locator"]["href"] == CHAPTER_TWO
        # A reading position is a caret rather than a selection, so it highlights
        # nothing and the text it carries is what sits on either side of it --
        # read out of the EPUB rather than approximated, which is what makes the
        # forward conversion exact where the reverse one is a search.
        assert resume["locator"]["text"]["highlight"] == ""
        assert SECOND_CHAPTER in resume["locator"]["text"]["after"]

    async def test_the_browser_read_more_recently_wins(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        readable_book: Book,
    ) -> None:
        """Should open at the browser's own stored locator when it is the later sighting.

        And hand it back whole. A locator the navigator itself produced needs no
        conversion and loses nothing on the way out, which is why a tie goes to
        it as well.
        """
        await self.a_koreader_session(
            db_session, readable_book, test_user.id, datetime(2026, 3, 1, 21, 0, tzinfo=UTC)
        )
        await put_position(
            client, readable_book.id, LAST_PARAGRAPH, datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
        )

        resume = await resume_for(client, readable_book.id)
        assert resume["source"] == "web"
        assert resume["xpoint"] == LAST_PARAGRAPH_XPOINT
        assert resume["position"] == LAST_PARAGRAPH_POSITION
        assert resume["locator"]["href"] == CHAPTER_ONE
        assert resume["locator"]["locations"]["cssSelector"] == LAST_PARAGRAPH_SELECTOR

    async def test_an_e_reader_alone_is_enough_to_resume_from(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        readable_book: Book,
    ) -> None:
        """Should open where the e-reader left off in a book never opened in a browser.

        The case the whole ticket is for: nothing has ever written a
        ``web_reading_positions`` row for this book, and the reader still lands
        where they stopped reading.
        """
        await self.a_koreader_session(
            db_session, readable_book, test_user.id, datetime(2026, 3, 1, 21, 0, tzinfo=UTC)
        )

        resume = await resume_for(client, readable_book.id)
        assert resume["source"] == "koreader"
        assert resume["locator"]["href"] == CHAPTER_TWO
        assert resume["recorded_at"] == "2026-03-01T21:00:00Z"

    async def test_the_browsers_own_session_never_beats_its_own_position(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should ignore the reading session a browser write makes when choosing where to open.

        This is the dedupe, and it is not merely tidiness. A web write records
        both a position and an ordinary ``reading_sessions`` row about the same
        moment -- but the session's ``end_time`` is the *server's* clock while
        the position's ``recorded_at`` is the *reader's*, so a reader whose
        clock runs a few minutes behind would have their exact stored locator
        thrown over for one re-derived from the xpointer beside it. The same
        place, arrived at worse.

        The clocks are pulled apart here on purpose: without the device filter
        the session below is a quarter of an hour "newer" than the position it
        was written with, and the answer would come back ``koreader``.
        """
        await put_position(
            client,
            readable_book.id,
            LAST_PARAGRAPH,
            datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            arriving=datetime(2026, 3, 1, 9, 15, tzinfo=UTC),
        )

        resume = await resume_for(client, readable_book.id)
        assert resume["source"] == "web"
        assert resume["locator"]["locations"]["cssSelector"] == LAST_PARAGRAPH_SELECTOR

    async def test_a_place_that_is_no_longer_in_the_book_is_reported_as_lost(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        readable_book: Book,
    ) -> None:
        """Should say the place could not be found rather than pretend the book was never read.

        An xpointer naming a spine document this EPUB does not have is what a
        replaced edition looks like from here (ADR-0004 §5). The canonical
        position is untouched and still comes back; what is missing is a view of
        it, and the reader is entitled to be told so instead of being dropped at
        page one with no explanation.
        """
        await self.a_koreader_session(
            db_session,
            readable_book,
            test_user.id,
            datetime(2026, 3, 1, 21, 0, tzinfo=UTC),
            xpoint=XPOINT_IN_ANOTHER_EDITION,
        )

        resume = await resume_for(client, readable_book.id)
        assert resume["locator"] is None
        assert resume["unresolved"] is True
        assert resume["source"] == "koreader"
        assert resume["xpoint"] == XPOINT_IN_ANOTHER_EDITION

    async def test_a_session_that_recorded_no_xpoint_says_nothing_about_where_to_open(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        readable_book: Book,
    ) -> None:
        """Should fall back to the browser's position when a sitting recorded no place.

        A KOReader session synced without positions has no xpointer at either
        end, so it is no candidate however recent it is -- and must not shadow
        the older sighting that does know where the reader was.
        """
        await put_position(
            client, readable_book.id, LAST_PARAGRAPH, datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        )
        await create_test_reading_session(
            db_session=db_session,
            book=readable_book,
            user_id=test_user.id,
            start_time=datetime(2026, 3, 5, 21, 0, tzinfo=UTC),
            device_id=KOREADER_DEVICE,
        )

        resume = await resume_for(client, readable_book.id)
        assert resume["source"] == "web"
        assert resume["xpoint"] == LAST_PARAGRAPH_XPOINT

    async def test_the_publication_cookie_opens_a_resume(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        readable_book: Book,
    ) -> None:
        """Should answer a resume to the credential an iframe-bound reader holds.

        The reader asks this on boot, when its access token may already have
        lapsed -- so the publication cookie has to be enough, exactly as it is
        for the manifest and every resource beside it (ADR-0004, Amendment 1).
        """
        await self.a_koreader_session(
            db_session, readable_book, test_user.id, datetime(2026, 3, 1, 21, 0, tzinfo=UTC)
        )
        minted = await start_publication_session(browser_client, test_user, readable_book.id)
        assert minted.status_code == status.HTTP_200_OK, minted.text

        response = await browser_client.get(position_url(readable_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["locator"]["href"] == CHAPTER_TWO
