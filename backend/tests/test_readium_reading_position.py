"""Reading position and reading sessions from the browser (M2.3, #742).

Two things are under test here and they are not the same thing.

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

Every locator here is built from ``tests/fixtures/minimal.epub`` and converted
for real -- no anchor service is faked, because the confidence a quote comes
back with is the thing being relied on. The fixture is built for it: chapter one
repeats one sentence in two paragraphs, so quoting that sentence alone is
genuinely ambiguous and quoting it with what precedes it is not.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
)
from src.models import Book, ReadingSession, User
from tests.conftest import create_test_book
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

# Where each quote is, and the CSS selector a navigator would have sent with it,
# so that a test names a paragraph once and every write of it is shaped like the
# real thing. A quote absent from here is written against chapter one with no
# selector at all, which is how the ambiguous cases below are made ambiguous.
PLACE_OF = {
    LAST_PARAGRAPH: (CHAPTER_ONE, LAST_PARAGRAPH_SELECTOR),
    SECOND_CHAPTER: (CHAPTER_TWO, SECOND_CHAPTER_SELECTOR),
}


def position_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/reading-position"


def a_page_turn(href: str = CHAPTER_ONE, progression: float = 0.0) -> dict[str, Any]:
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
            "position": 1,
        },
    }


def locator(quote: str, before: str | None = None, progression: float = 0.5) -> dict[str, Any]:
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
) -> Response:
    """Write a position the way the reader does: a locator and the moment it was seen."""
    return await put_locator(client, book_id, locator(quote, before=before), at, closing)


async def put_locator(
    client: AsyncClient,
    book_id: int,
    body: dict[str, Any],
    at: datetime,
    closing: bool = False,
) -> Response:
    """Write one locator, whatever shape it is in."""
    return await client.put(
        position_url(book_id),
        json={"locator": body, "recorded_at": at.isoformat(), "closing": closing},
    )


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

    async def test_a_book_never_read_here_has_no_position(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should answer null rather than 404: an unread book is not a missing one."""
        response = await client.get(position_url(readable_book.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None

    async def test_a_later_write_replaces_an_earlier_one(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should move the stored position as the reader moves."""
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, LAST_PARAGRAPH, start)

        await put_position(client, readable_book.id, SECOND_CHAPTER, start + timedelta(minutes=2))

        stored = (await client.get(position_url(readable_book.id))).json()
        assert stored["position"] == SECOND_CHAPTER_POSITION

    async def test_a_write_that_arrives_late_does_not_rewind_the_reader(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should keep the newer position when an older observation lands after it.

        The debounced write and the one a closing tab sends race by design, so
        the loser must be harmless rather than an error the page has to handle.
        """
        start = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        await put_position(client, readable_book.id, SECOND_CHAPTER, start + timedelta(minutes=5))

        late = await put_position(client, readable_book.id, LAST_PARAGRAPH, start)

        assert late.status_code == status.HTTP_200_OK
        assert late.json()["position"] == SECOND_CHAPTER_POSITION
        stored = (await client.get(position_url(readable_book.id))).json()
        assert stored["position"] == SECOND_CHAPTER_POSITION

    async def test_a_clock_that_runs_ahead_cannot_claim_the_future(
        self, client: AsyncClient, readable_book: Book
    ) -> None:
        """Should record a position claimed for next week as recorded now.

        Left alone, a fast clock would both invent reading time and lock the
        reader out of writing again until the date it claimed.
        """
        before = datetime.now(UTC)

        response = await put_position(
            client, readable_book.id, LAST_PARAGRAPH, before + timedelta(days=7)
        )

        assert response.status_code == status.HTTP_200_OK
        recorded = datetime.fromisoformat(response.json()["updated_at"])
        assert before <= recorded <= datetime.now(UTC)


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
        assert (await client.get(position_url(readable_book.id))).json() is None

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
