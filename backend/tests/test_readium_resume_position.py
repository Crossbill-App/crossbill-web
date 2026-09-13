"""The reading-position read -- where the web reader opens a book (R4.4, #830).

Everything answered here was stored when the reader was there: the browser's own
locator on ``web_reading_positions``, and R4.2's locator columns on
``reading_sessions``. So every fixture writes those columns directly, the way the
write path and the sync leave them, and no test puts an EPUB on disk --
``minimal.epub`` is only ever the book's stored publication, whose digest decides
whether a stored locator still applies.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.application.web_reader.anchors import Locator, LocatorLocations, LocatorText
from src.domain.common.devices import WEB_READER_DEVICE_ID
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from tests.readium_helpers import (
    another_users_indexed_book,
    hold_publication_cookie,
    parse_fixture,
    store_fixture,
)

MINIMAL_DIGEST = parse_fixture("minimal").content_hash
OTHER_BOOK_DIGEST = parse_fixture("fixed_layout").content_hash

MEDIA_TYPE = "application/xhtml+xml"
CH1_XPOINT = "/body/DocFragment[1]/body/div[1]/p[4]"
CH2_XPOINT = "/body/DocFragment[2]/body/div[1]/p[1]"

NOON = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
NOON_ON_THE_WIRE = "2026-05-01T12:00:00Z"

# The navigator's own document, including the two fields nothing server-side
# derives. Every field here is one the schema declares, so it all comes back.
BROWSER_LOCATOR: dict[str, Any] = {
    "href": "resources/OEBPS/chapter2.xhtml",
    "type": MEDIA_TYPE,
    "locations": {
        "position": 12,
        "progression": 0.4,
        "totalProgression": 0.65,
        "cssSelector": "#second > p:nth-child(2)",
    },
    "text": {"highlight": "Morning arrived without ceremony"},
}

# An e-reader's, in the EPUB's own container coordinates, as R4.2 stored it.
DEVICE_LOCATOR = Locator(
    href="OEBPS/chapter1.xhtml",
    type=MEDIA_TYPE,
    locations=LocatorLocations(progression=0.25, css_selector="#intro > p:nth-child(4)"),
    text=LocatorText(before="before ", highlight="The lantern went out at midnight"),
)

# A second one, so which of two sessions was answered is visible in the response.
OTHER_DEVICE_LOCATOR = Locator(
    href="OEBPS/chapter2.xhtml",
    type=MEDIA_TYPE,
    locations=LocatorLocations(progression=0.75, css_selector="#second > p:nth-child(1)"),
    text=LocatorText(highlight="Morning arrived without ceremony"),
)


def url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/reading-position"


@pytest.fixture
async def indexed_book(db_session: AsyncSession, test_book: models.Book) -> models.Book:
    """The user's own book, with ``minimal.epub`` as its stored publication."""
    await store_fixture(db_session, test_book, "minimal")
    return test_book


async def store_browser_position(
    db_session: AsyncSession,
    book: models.Book,
    user_id: int,
    recorded_at: datetime,
    locator: dict[str, Any] | None = None,
    source_hash: str = MINIMAL_DIGEST,
) -> None:
    """Put the row the browser's own write leaves behind in place."""
    db_session.add(
        models.WebReadingPosition(
            user_id=user_id,
            book_id=book.id,
            locator=locator if locator is not None else BROWSER_LOCATOR,
            xpoint=CH2_XPOINT,
            locator_source_hash=source_hash,
            updated_at=recorded_at,
            recorded_at=recorded_at,
        )
    )
    await db_session.commit()


async def store_session(
    db_session: AsyncSession,
    book: models.Book,
    user_id: int,
    end_time: datetime,
    locator: Locator | None = DEVICE_LOCATOR,
    source_hash: str | None = MINIMAL_DIGEST,
    device_id: str | None = "kobo-clara",
    end_xpoint: str | None = CH1_XPOINT,
) -> None:
    """Put a synced reading session in place, with the locator columns R4.2 writes."""
    session = models.ReadingSession(
        user_id=user_id,
        book_id=book.id,
        start_time=end_time - timedelta(minutes=20),
        end_time=end_time,
        start_xpoint=end_xpoint,
        end_xpoint=end_xpoint,
        end_locator=locator.to_dict() if locator else None,
        locator_source_hash=source_hash,
        device_id=device_id,
        content_hash=f"hash-{end_time.isoformat()}-{device_id}-{book.id}",
    )
    db_session.add(session)
    await db_session.commit()


async def resume(client: AsyncClient, book: models.Book) -> dict[str, Any]:
    response = await client.get(url(book.id))
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def moment(answer: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(answer["recorded_at"])


async def test_a_book_read_nowhere_answers_a_position_of_none_rather_than_404(
    client: AsyncClient, indexed_book: models.Book
) -> None:
    """Never opened is an ordinary state of an ordinary book."""
    assert await resume(client, indexed_book) == {"unresolved": False}


async def test_a_browser_position_is_answered_with_the_locator_the_navigator_sent(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await store_browser_position(db_session, indexed_book, test_user.id, NOON)

    answer = await resume(client, indexed_book)

    assert answer["source"] == "web"
    assert answer["unresolved"] is False
    assert answer["locator"] == BROWSER_LOCATOR
    # Without the zone marker a browser reads the moment as local time, so a
    # reader two hours east of UTC would be told they read two hours ago.
    assert answer["recorded_at"] == NOON_ON_THE_WIRE


async def test_a_device_session_is_answered_with_its_href_pointed_at_the_serving_url(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await store_session(db_session, indexed_book, test_user.id, NOON)

    answer = await resume(client, indexed_book)

    assert answer["source"] == "koreader"
    assert answer["unresolved"] is False
    assert answer["locator"] == {
        "href": "resources/OEBPS/chapter1.xhtml",
        "type": MEDIA_TYPE,
        "locations": {"progression": 0.25, "cssSelector": "#intro > p:nth-child(4)"},
        "text": {"before": "before ", "highlight": "The lantern went out at midnight"},
    }
    assert answer["recorded_at"] == NOON_ON_THE_WIRE


async def test_a_device_session_later_than_the_browser_position_wins(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await store_browser_position(db_session, indexed_book, test_user.id, NOON)
    await store_session(db_session, indexed_book, test_user.id, NOON + timedelta(minutes=1))

    answer = await resume(client, indexed_book)

    assert answer["source"] == "koreader"
    assert answer["locator"]["href"] == "resources/OEBPS/chapter1.xhtml"
    assert moment(answer) == NOON + timedelta(minutes=1)


async def test_a_browser_position_later_than_the_device_session_wins(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await store_session(db_session, indexed_book, test_user.id, NOON)
    await store_browser_position(
        db_session, indexed_book, test_user.id, NOON + timedelta(minutes=1)
    )

    answer = await resume(client, indexed_book)

    assert answer["source"] == "web"
    assert answer["locator"] == BROWSER_LOCATOR
    assert moment(answer) == NOON + timedelta(minutes=1)


async def test_the_latest_of_several_device_sessions_is_the_one_answered(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await store_session(db_session, indexed_book, test_user.id, NOON + timedelta(hours=1))
    await store_session(
        db_session,
        indexed_book,
        test_user.id,
        NOON,
        locator=None,
        device_id="kindle",
    )

    answer = await resume(client, indexed_book)

    assert answer["unresolved"] is False
    assert moment(answer) == NOON + timedelta(hours=1)


async def test_the_last_written_of_two_sessions_ending_together_is_the_one_answered(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """Two devices can report the same end time, and one place has to come back."""
    await store_session(db_session, indexed_book, test_user.id, NOON)
    await store_session(
        db_session,
        indexed_book,
        test_user.id,
        NOON,
        locator=OTHER_DEVICE_LOCATOR,
        device_id="kindle",
    )

    answer = await resume(client, indexed_book)

    assert answer["locator"]["href"] == "resources/OEBPS/chapter2.xhtml"


async def test_a_tie_goes_to_the_browsers_own_locator(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """At the same moment the exact locator beats one reconstructed beside it."""
    await store_browser_position(db_session, indexed_book, test_user.id, NOON)
    await store_session(db_session, indexed_book, test_user.id, NOON)

    answer = await resume(client, indexed_book)

    assert answer["source"] == "web"
    assert answer["locator"] == BROWSER_LOCATOR


async def test_a_session_whose_locator_was_never_stored_says_the_place_was_lost(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await store_session(db_session, indexed_book, test_user.id, NOON, locator=None)

    answer = await resume(client, indexed_book)

    assert answer["source"] == "koreader"
    assert answer["unresolved"] is True
    assert "locator" not in answer
    assert moment(answer) == NOON


async def test_a_session_locator_derived_from_another_epub_is_withheld_not_served(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await store_session(db_session, indexed_book, test_user.id, NOON, source_hash=OTHER_BOOK_DIGEST)

    answer = await resume(client, indexed_book)

    assert answer["source"] == "koreader"
    assert answer["unresolved"] is True
    assert "locator" not in answer


async def test_a_browser_position_from_another_epub_is_not_restored(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """The file under the book was replaced, so the locator names a page it no longer has."""
    await store_browser_position(
        db_session, indexed_book, test_user.id, NOON, source_hash=OTHER_BOOK_DIGEST
    )

    answer = await resume(client, indexed_book)

    assert answer["source"] == "web"
    assert answer["unresolved"] is True
    assert "locator" not in answer


async def test_a_position_in_a_book_with_no_publication_cannot_be_placed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    test_book: models.Book,
) -> None:
    await store_browser_position(db_session, test_book, test_user.id, NOON)

    answer = await resume(client, test_book)

    assert answer["unresolved"] is True
    assert "locator" not in answer


async def test_a_session_the_web_reader_wrote_is_no_device_candidate(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """It describes the same moment as the position beside it, by the server's clock."""
    await store_browser_position(db_session, indexed_book, test_user.id, NOON)
    await store_session(
        db_session,
        indexed_book,
        test_user.id,
        NOON + timedelta(seconds=30),
        device_id=WEB_READER_DEVICE_ID,
    )

    answer = await resume(client, indexed_book)

    assert answer["source"] == "web"
    assert answer["locator"] == BROWSER_LOCATOR
    assert moment(answer) == NOON


async def test_a_session_that_named_no_device_is_still_a_candidate(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """A sync may omit the device, and a nameless one is not the web reader."""
    await store_browser_position(db_session, indexed_book, test_user.id, NOON)
    await store_session(
        db_session,
        indexed_book,
        test_user.id,
        NOON + timedelta(minutes=1),
        device_id=None,
    )

    answer = await resume(client, indexed_book)

    assert answer["source"] == "koreader"
    assert answer["locator"]["href"] == "resources/OEBPS/chapter1.xhtml"
    assert moment(answer) == NOON + timedelta(minutes=1)


async def test_a_session_with_no_end_xpointer_is_no_candidate_however_recent(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """It never said where the reader got to, which is not the same as losing the place."""
    await store_browser_position(db_session, indexed_book, test_user.id, NOON)
    await store_session(
        db_session,
        indexed_book,
        test_user.id,
        NOON + timedelta(hours=1),
        locator=None,
        end_xpoint=None,
    )

    answer = await resume(client, indexed_book)

    assert answer["source"] == "web"
    assert answer["locator"] == BROWSER_LOCATOR


async def test_another_users_position_on_this_book_is_not_answered(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """A position row carries its own reader, and the book id alone would reach this one."""
    stranger = models.User(email="stranger-position@test.com", hashed_password="x")
    db_session.add(stranger)
    await db_session.commit()
    await store_browser_position(db_session, indexed_book, stranger.id, NOON + timedelta(hours=1))
    await store_session(db_session, indexed_book, test_user.id, NOON)

    answer = await resume(client, indexed_book)

    assert answer["source"] == "koreader"
    assert moment(answer) == NOON


async def test_another_users_session_on_this_book_is_not_answered(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    stranger = models.User(email="stranger-resume@test.com", hashed_password="x")
    db_session.add(stranger)
    await db_session.commit()
    await store_session(db_session, indexed_book, stranger.id, NOON + timedelta(hours=1))
    await store_browser_position(db_session, indexed_book, test_user.id, NOON)

    answer = await resume(client, indexed_book)

    assert answer["source"] == "web"
    assert moment(answer) == NOON


async def test_the_read_touches_no_epub_and_runs_no_parse(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await store_session(db_session, indexed_book, test_user.id, NOON)

    def refuse(*_: object, **__: object) -> None:
        pytest.fail("the reading-position read touched the book's EPUB")

    monkeypatch.setattr(FileRepository, "get_epub", refuse)
    monkeypatch.setattr(EpubParserService, "parse_publication", refuse)

    answer = await resume(client, indexed_book)

    assert answer["locator"]["href"] == "resources/OEBPS/chapter1.xhtml"


async def test_another_users_book_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    theirs = await another_users_indexed_book(db_session)

    response = await client.get(url(theirs.id))

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_the_publication_cookie_alone_is_refused(
    browser_client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    test_book: models.Book,
) -> None:
    await hold_publication_cookie(browser_client, db_session, test_user.id, test_book)

    response = await browser_client.get(url(test_book.id))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
