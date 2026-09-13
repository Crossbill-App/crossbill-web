"""The whole-book highlight-locator route (R4.3, #829).

Everything it answers with was written by R4.2's ingest, so every fixture here
puts the locator columns in the state an ingest would have left them in and the
assertions are against the response. ``minimal.epub`` is the book's publication
and ``fixed_layout.epub`` the second one whose digest makes a locator stale.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.application.web_reader.anchors import Locator, LocatorLocations, LocatorText
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
)
from tests.conftest import create_test_highlight
from tests.readium_helpers import another_users_book, parse_fixture, store_fixture
from tests.test_readium_cookie_access import present
from tests.test_readium_session import start_session

MINIMAL_DIGEST = parse_fixture("minimal").content_hash
OTHER_BOOK_DIGEST = parse_fixture("fixed_layout").content_hash

FIRST_QUOTE = "The lantern went out at midnight"
SECOND_QUOTE = "Morning arrived without ceremony"


def url(book_id: int) -> str:
    return f"/api/v1/books/{book_id}/highlight-locators"


def locator(href: str, quote: str, selector: str) -> Locator:
    return Locator(
        href=href,
        type="application/xhtml+xml",
        locations=LocatorLocations(progression=0.25, css_selector=selector),
        text=LocatorText(before="before ", highlight=quote, after=" after"),
    )


FIRST_LOCATOR = locator("OEBPS/chapter1.xhtml", FIRST_QUOTE, "#intro > p:nth-child(4)")
SECOND_LOCATOR = locator("OEBPS/chapter2.xhtml", SECOND_QUOTE, "#second > p:nth-child(2)")


async def add_highlight(
    db_session: AsyncSession,
    book: models.Book,
    user_id: int,
    text: str,
    stored: Locator | None = None,
    source_hash: str | None = None,
    deleted: bool = False,
) -> models.Highlight:
    """Create a highlight whose locator columns are already in the given state."""
    highlight = await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=user_id,
        text=text,
        datetime_str="2024-01-15 14:30:22",
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    highlight.locator = stored.to_dict() if stored else None
    highlight.locator_source_hash = source_hash
    await db_session.commit()
    await db_session.refresh(highlight)
    return highlight


async def items(client: AsyncClient, book: models.Book) -> list[dict[str, Any]]:
    response = await client.get(url(book.id))
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["items"]


@pytest.fixture
async def indexed_book(db_session: AsyncSession, test_book: models.Book) -> models.Book:
    """The user's own book, with ``minimal.epub`` as its stored publication."""
    await store_fixture(db_session, test_book, "minimal")
    return test_book


async def test_a_fresh_locator_is_served_in_the_coordinates_the_manifest_publishes(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    first = await add_highlight(
        db_session, indexed_book, test_user.id, FIRST_QUOTE, FIRST_LOCATOR, MINIMAL_DIGEST
    )
    second = await add_highlight(
        db_session, indexed_book, test_user.id, SECOND_QUOTE, SECOND_LOCATOR, MINIMAL_DIGEST
    )

    served = await items(client, indexed_book)

    assert [item["highlight_id"] for item in served] == [first.id, second.id]
    assert all("unavailable" not in item for item in served)
    assert served[0]["locator"]["href"] == "resources/OEBPS/chapter1.xhtml"
    assert served[0]["locator"]["type"] == "application/xhtml+xml"
    assert served[0]["locator"]["locations"]["cssSelector"] == "#intro > p:nth-child(4)"
    assert served[0]["locator"]["locations"]["progression"] == 0.25
    assert served[0]["locator"]["text"]["highlight"] == FIRST_QUOTE
    assert served[1]["locator"]["href"] == "resources/OEBPS/chapter2.xhtml"
    assert served[1]["locator"]["locations"]["cssSelector"] == "#second > p:nth-child(2)"
    assert served[1]["locator"]["text"]["highlight"] == SECOND_QUOTE


async def test_a_book_with_no_publication_answers_no_ebook_rather_than_404(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    test_book: models.Book,
) -> None:
    await add_highlight(db_session, test_book, test_user.id, FIRST_QUOTE)
    await add_highlight(
        db_session, test_book, test_user.id, SECOND_QUOTE, SECOND_LOCATOR, MINIMAL_DIGEST
    )

    served = await items(client, test_book)

    assert [item["unavailable"] for item in served] == ["no_ebook", "no_ebook"]
    assert all("locator" not in item for item in served)


async def test_a_highlight_the_ingest_could_not_place_is_unresolved(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await add_highlight(db_session, indexed_book, test_user.id, FIRST_QUOTE, None, MINIMAL_DIGEST)

    served = await items(client, indexed_book)

    assert served[0]["unavailable"] == "unresolved"
    assert "locator" not in served[0]


async def test_a_locator_derived_from_another_epub_is_withheld_not_served(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await add_highlight(
        db_session, indexed_book, test_user.id, FIRST_QUOTE, FIRST_LOCATOR, OTHER_BOOK_DIGEST
    )

    served = await items(client, indexed_book)

    assert served[0]["unavailable"] == "unresolved"
    assert "locator" not in served[0]


async def test_a_deleted_highlight_is_absent_while_its_live_sibling_is_listed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    await add_highlight(
        db_session,
        indexed_book,
        test_user.id,
        FIRST_QUOTE,
        FIRST_LOCATOR,
        MINIMAL_DIGEST,
        deleted=True,
    )
    live = await add_highlight(
        db_session, indexed_book, test_user.id, SECOND_QUOTE, SECOND_LOCATOR, MINIMAL_DIGEST
    )

    served = await items(client, indexed_book)

    assert [item["highlight_id"] for item in served] == [live.id]


async def test_a_book_with_a_publication_and_no_highlights_answers_an_empty_list(
    client: AsyncClient, indexed_book: models.Book
) -> None:
    assert await items(client, indexed_book) == []


async def test_another_users_highlight_on_this_book_is_not_listed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
) -> None:
    """A highlight carries its own user, and the book id alone would reach this one."""
    stranger = models.User(email="stranger-locators@test.com", hashed_password="x")
    db_session.add(stranger)
    await db_session.commit()
    await add_highlight(
        db_session, indexed_book, stranger.id, FIRST_QUOTE, FIRST_LOCATOR, MINIMAL_DIGEST
    )
    mine = await add_highlight(
        db_session, indexed_book, test_user.id, SECOND_QUOTE, SECOND_LOCATOR, MINIMAL_DIGEST
    )

    served = await items(client, indexed_book)

    assert [item["highlight_id"] for item in served] == [mine.id]


async def test_another_users_book_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    theirs = await another_users_book(db_session)
    await store_fixture(db_session, theirs, "minimal")

    response = await client.get(url(theirs.id))

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_the_publication_cookie_is_not_a_key_to_this_route(
    browser_client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    test_book: models.Book,
) -> None:
    await store_fixture(db_session, test_book, "minimal")
    minted = await start_session(browser_client, test_user.id, test_book.id)
    # `present` plants the cookie under the whole API and under the host httpx's
    # jar actually stores -- see its own `COOKIE_DOMAIN` note -- so what is under
    # test is the refusal rather than the browser never offering it.
    present(browser_client, minted.cookies[PUBLICATION_COOKIE_NAME])

    response = await browser_client.get(url(test_book.id))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


async def test_the_route_reads_no_epub_and_runs_no_parse(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    indexed_book: models.Book,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_highlight(
        db_session, indexed_book, test_user.id, FIRST_QUOTE, FIRST_LOCATOR, MINIMAL_DIGEST
    )

    def refuse(*_: object, **__: object) -> None:
        pytest.fail("the highlight-locator route touched the book's EPUB")

    monkeypatch.setattr(FileRepository, "get_epub", refuse)
    monkeypatch.setattr(EpubParserService, "parse_publication", refuse)

    served = await items(client, indexed_book)

    assert served[0]["locator"]["href"] == "resources/OEBPS/chapter1.xhtml"
