"""The reading-position write -- what a browser stores, and the sitting it opens (R4.4, #830).

``minimal.epub`` is the book throughout. Its chapter one holds the same sentence
twice, which is what makes an ambiguous quote observable, and each chapter holds one
sentence that occurs nowhere else.

Every write is driven through an overridden ``reader_now``: the store orders writes on
the server's clock, so two writes a test means to be apart have to be apart.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.application.web_reader.queries.publication_positions import MAX_PUBLICATION_POSITIONS
from src.domain.common.devices import WEB_READER_DEVICE_ID
from src.domain.common.time import as_aware
from src.infrastructure.reading.routers.reader_clock import reader_now
from src.infrastructure.web_reader.services.publication_token_service import (
    create_publication_token,
)
from src.main import app
from tests.conftest import create_test_book
from tests.readium_helpers import another_users_book, fixture_bytes
from tests.test_readium_cookie_access import present
from tests.test_readium_manifest import store_epub

CH1_HREF = "resources/OEBPS/chapter1.xhtml"
CH2_HREF = "resources/OEBPS/chapter2.xhtml"
MEDIA_TYPE = "application/xhtml+xml"

# One sentence per chapter that occurs nowhere else in the book, and the place each
# one resolves to. `THE_SAME_TWICE` is chapter one's repeated sentence.
CH1_QUOTE = "Nothing else in the house moved"
CH1_XPOINT = "/body/DocFragment[1]/body/div[1]/p[4]"
CH1_POSITION = {"index": 10, "char_index": 0}
CH1_SELECTOR = "#intro > p:nth-child(5)"
CH2_QUOTE = "Morning arrived without ceremony"
CH2_XPOINT = "/body/DocFragment[2]/body/div[1]/p[1]"
CH2_POSITION = {"index": 16, "char_index": 0}
CH2_HEADING_XPOINT = "/body/DocFragment[2]/body/div[1]/h1[1]"
THE_SAME_TWICE = "The lantern went out at midnight"

IDLE_SECONDS = 1800
START = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


def url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/reading-position"


def locator(
    href: str,
    quote: str | None = None,
    selector: str | None = None,
    progression: float | None = None,
    fragments: list[str] | None = None,
    position: int | None = None,
) -> dict[str, Any]:
    """One Readium Locator as a navigator sends it, carrying only what is given."""
    locations: dict[str, Any] = {}
    if progression is not None:
        locations["progression"] = progression
    if selector is not None:
        locations["cssSelector"] = selector
    if fragments is not None:
        locations["fragments"] = fragments
    if position is not None:
        locations["position"] = position
    return {
        "href": href,
        "type": MEDIA_TYPE,
        "locations": locations,
        "text": {"highlight": quote} if quote is not None else {},
    }


class Clock:
    """The server clock the route reads, under the test's control."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock(client: AsyncClient) -> Iterator[Clock]:
    """Pin ``reader_now``. Depends on ``client``, whose teardown clears the overrides."""
    pinned = Clock(START)
    app.dependency_overrides[reader_now] = lambda: pinned.now
    yield pinned
    del app.dependency_overrides[reader_now]


@pytest.fixture
async def readable_book(
    db_session: AsyncSession, test_book: models.Book, storage_dir: Path
) -> models.Book:
    """The user's own book, with ``minimal.epub`` on disk to place positions against."""
    await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal"))
    return test_book


async def write(
    client: AsyncClient,
    book: models.Book,
    body: dict[str, Any],
    recorded_at: datetime | None = None,
    closing: bool = False,
) -> Response:
    return await client.put(
        url(book.id),
        json={
            "locator": body,
            "recorded_at": (recorded_at or START).isoformat(),
            "closing": closing,
        },
    )


async def accepted(
    client: AsyncClient,
    book: models.Book,
    body: dict[str, Any],
    recorded_at: datetime | None = None,
    closing: bool = False,
) -> dict[str, Any]:
    response = await write(client, book, body, recorded_at, closing)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def moved_on(
    clock: Clock,
    seconds: int,
    client: AsyncClient,
    book: models.Book,
    body: dict[str, Any],
    closing: bool = False,
) -> datetime:
    """Carry the reader forward: advance the clock, then write from the moment it now is."""
    clock.advance(seconds)
    await accepted(client, book, body, recorded_at=clock.now, closing=closing)
    return clock.now


async def stored_position(
    db_session: AsyncSession, book: models.Book
) -> models.WebReadingPosition | None:
    # `populate_existing` rather than `expire_all`: the request wrote through this same
    # session, and an instance it already holds would otherwise come back unrefreshed.
    rows = await db_session.execute(
        select(models.WebReadingPosition)
        .filter_by(book_id=book.id)
        .execution_options(populate_existing=True)
    )
    return rows.scalars().one_or_none()


async def stored_sessions(
    db_session: AsyncSession, book: models.Book
) -> list[models.ReadingSession]:
    rows = await db_session.execute(
        select(models.ReadingSession)
        .filter_by(book_id=book.id)
        .order_by(models.ReadingSession.start_time)
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().all())


async def test_a_write_stores_the_locator_the_xpointer_and_the_position(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    body = await accepted(
        client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE, progression=0.8, position=3)
    )

    assert body["xpoint"] == CH1_XPOINT
    assert body["position"] == CH1_POSITION
    assert body["locator"]["href"] == CH1_HREF
    assert body["locator"]["text"]["highlight"] == CH1_QUOTE
    row = await stored_position(db_session, readable_book)
    assert row is not None
    assert row.xpoint == CH1_XPOINT
    assert row.locator["href"] == CH1_HREF
    assert row.locator["locations"]["position"] == 3
    assert row.locator_source_hash


async def test_a_write_opens_a_reading_session_the_position_points_at(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    await accepted(
        client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE, position=3), recorded_at=START
    )

    sessions = await stored_sessions(db_session, readable_book)
    assert len(sessions) == 1
    session = sessions[0]
    assert session.device_id == WEB_READER_DEVICE_ID
    assert session.start_xpoint == CH1_XPOINT
    assert session.start_page == 3
    assert session.end_page == 3
    assert session.end_position == [CH1_POSITION["index"], CH1_POSITION["char_index"]]
    row = await stored_position(db_session, readable_book)
    assert row is not None
    assert row.reading_session_id == session.id


async def test_a_session_carries_the_locators_the_browser_sent(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    await accepted(client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE))
    await moved_on(clock, 60, client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE))

    session = (await stored_sessions(db_session, readable_book))[0]
    # Stored in the EPUB's own coordinates, as R4.2's derived locators are: the start
    # keeps where the sitting opened while the end follows the reader.
    assert session.start_locator is not None
    assert session.start_locator["href"] == "OEBPS/chapter1.xhtml"
    assert session.end_locator is not None
    assert session.end_locator["href"] == "OEBPS/chapter2.xhtml"
    assert session.locator_source_hash


async def test_a_second_write_inside_the_idle_window_extends_the_same_session(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    await accepted(client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE, position=3))

    later = await moved_on(
        clock, IDLE_SECONDS, client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE, position=9)
    )

    sessions = await stored_sessions(db_session, readable_book)
    assert len(sessions) == 1
    assert as_aware(sessions[0].end_time) == later
    assert sessions[0].end_page == 9
    assert sessions[0].end_xpoint == CH2_XPOINT


async def test_a_write_after_the_idle_window_starts_a_new_session(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    await accepted(client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE))

    await moved_on(
        clock, IDLE_SECONDS + 1, client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE)
    )

    sessions = await stored_sessions(db_session, readable_book)
    assert len(sessions) == 2
    assert sessions[1].start_xpoint == CH2_XPOINT
    row = await stored_position(db_session, readable_book)
    assert row is not None
    assert row.reading_session_id == sessions[1].id


async def test_closing_ends_the_session_so_the_next_write_starts_a_new_one(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    await accepted(client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE))
    await moved_on(
        clock, 60, client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE), closing=True
    )

    closed = await stored_position(db_session, readable_book)
    assert closed is not None
    assert closed.reading_session_id is None

    await moved_on(clock, 60, client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE))

    sessions = await stored_sessions(db_session, readable_book)
    assert len(sessions) == 2


async def test_an_older_recorded_at_does_not_move_the_position(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    # The first write is made at its own moment, not ahead of it: a position is never
    # stored as later than the request that carried it.
    await moved_on(clock, 60, client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE))
    clock.advance(10)

    body = await accepted(
        client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE), recorded_at=START
    )

    assert body["xpoint"] == CH2_XPOINT
    row = await stored_position(db_session, readable_book)
    assert row is not None
    assert row.xpoint == CH2_XPOINT
    # The reader is still here, so the sitting runs on even though it learns nothing
    # about where they are.
    session = (await stored_sessions(db_session, readable_book))[0]
    assert as_aware(session.end_time) == START + timedelta(seconds=70)
    assert session.end_xpoint == CH2_XPOINT


async def test_a_clock_running_ahead_does_not_freeze_the_position(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    """Unclamped, a sighting stamped next year would refuse every honest write until then."""
    await accepted(
        client,
        readable_book,
        locator(CH1_HREF, quote=CH1_QUOTE),
        recorded_at=START + timedelta(days=365),
    )

    await moved_on(clock, 60, client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE))

    row = await stored_position(db_session, readable_book)
    assert row is not None
    assert row.xpoint == CH2_XPOINT


async def test_a_write_the_server_clock_cannot_separate_is_answered_not_refused(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    """The write a closing tab sends and the one a page turn sends race by design."""
    await accepted(client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE), recorded_at=clock.now)

    body = await accepted(
        client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE), recorded_at=clock.now
    )

    assert body["xpoint"] == CH2_XPOINT
    assert len(await stored_sessions(db_session, readable_book)) == 1


async def test_a_jump_back_across_the_book_starts_a_new_session(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    await accepted(client, readable_book, locator(CH2_HREF, quote=CH2_QUOTE))

    await moved_on(clock, 60, client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE))

    sessions = await stored_sessions(db_session, readable_book)
    assert len(sessions) == 2
    assert sessions[1].start_xpoint == CH1_XPOINT


async def test_a_locator_that_will_not_convert_is_rejected_and_stores_nothing(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    response = await write(client, readable_book, locator("resources/OEBPS/chapter9.xhtml"))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert await stored_position(db_session, readable_book) is None
    assert await stored_sessions(db_session, readable_book) == []


async def test_a_quote_the_book_holds_twice_is_too_weak_to_store(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    response = await write(client, readable_book, locator(CH1_HREF, quote=THE_SAME_TWICE))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert await stored_position(db_session, readable_book) is None


async def test_a_textless_locator_resolves_through_the_element_it_names(
    client: AsyncClient, readable_book: models.Book, clock: Clock
) -> None:
    body = await accepted(client, readable_book, locator(CH1_HREF, selector=CH1_SELECTOR))

    assert body["xpoint"] == CH1_XPOINT


async def test_a_textless_locator_resolves_through_its_progression_when_it_names_none(
    client: AsyncClient, readable_book: models.Book, clock: Clock
) -> None:
    body = await accepted(client, readable_book, locator(CH2_HREF, progression=0.0))

    assert body["xpoint"] == CH2_HEADING_XPOINT


async def test_a_locator_with_no_text_no_element_and_no_progression_is_rejected(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    response = await write(client, readable_book, locator(CH1_HREF))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert await stored_position(db_session, readable_book) is None


async def test_a_book_whose_file_cannot_be_read_is_answered_apart_from_a_bad_locator(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    storage_dir: Path,
    clock: Clock,
) -> None:
    book = await create_test_book(db_session=db_session, user_id=test_user.id, title="Corrupt")
    await store_epub(db_session, book, storage_dir, b"not an archive at all", "corrupt.epub")

    response = await write(client, book, locator(CH1_HREF, quote=CH1_QUOTE))

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text
    assert await stored_position(db_session, book) is None


async def test_a_book_with_no_epub_is_not_found(
    client: AsyncClient, db_session: AsyncSession, test_book: models.Book, clock: Clock
) -> None:
    # The same answer the manifest gives such a book: there is nothing to read, and
    # nothing the reader can do about it that knowing more would help with.
    response = await write(client, test_book, locator(CH1_HREF, quote=CH1_QUOTE))

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_another_users_book_is_not_found(
    client: AsyncClient, db_session: AsyncSession, clock: Clock
) -> None:
    theirs = await another_users_book(db_session)

    response = await write(client, theirs, locator(CH1_HREF, quote=CH1_QUOTE))

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_the_publication_cookie_alone_is_refused(
    browser_client: AsyncClient, db_session: AsyncSession, test_user: models.User
) -> None:
    book = await create_test_book(db_session=db_session, user_id=test_user.id, title="Cookie Only")
    token = create_publication_token(
        user_id=test_user.id, book_id=book.id, not_after=datetime.now(UTC) + timedelta(hours=1)
    )
    present(browser_client, token.value)

    response = await write(browser_client, book, locator(CH1_HREF, quote=CH1_QUOTE))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


async def test_a_non_finite_progression_is_read_as_no_progression(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, clock: Clock
) -> None:
    # Degraded, not refused: a 422 quoting `NaN` back would not serialise, so the
    # locator is judged on what else it carries -- here, nothing.
    response = await client.put(
        url(readable_book.id),
        content=(
            '{"locator": {"href": "' + CH1_HREF + '", "type": "' + MEDIA_TYPE + '",'
            ' "locations": {"progression": NaN}, "text": {}},'
            ' "recorded_at": "' + START.isoformat() + '", "closing": false}'
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert response.json()["error"] == "unprocessable_entity"
    assert await stored_position(db_session, readable_book) is None


@pytest.mark.parametrize("page", [MAX_PUBLICATION_POSITIONS + 1, 0, -1])
async def test_a_page_off_the_position_list_costs_the_label_not_the_reading(
    client: AsyncClient,
    db_session: AsyncSession,
    readable_book: models.Book,
    clock: Clock,
    page: int,
) -> None:
    """The page indexes a list this API served; the position beside it is still good."""
    await accepted(client, readable_book, locator(CH1_HREF, quote=CH1_QUOTE, position=page))

    row = await stored_position(db_session, readable_book)
    assert row is not None
    assert row.xpoint == CH1_XPOINT
    session = (await stored_sessions(db_session, readable_book))[0]
    assert session.start_page is None
    assert session.end_page is None
