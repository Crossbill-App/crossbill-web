"""Tests for the ingest paths that derive a Readium Locator and store it.

Only the KOReader highlight sync derives one so far; the reading-session sync
and the EPUB-upload backfill join this file as they land. A locator has no read
route until R4.3 (#829), so every assertion here is against the stored row.

The fixture book is ``tests/fixtures/minimal.epub``, and the xpointers below are
the ones the adapter's own tests verified against it.
"""

import hashlib
from collections.abc import Hashable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.anchors import AnchorResolutionError, Locator
from src.domain.common.value_objects.xpoint import XPointRange
from src.infrastructure.web_reader.services.xpoint_cfi_position_anchor_service import (
    XPointCfiPositionAnchorService,
)
from tests.conftest import create_test_book, create_test_highlight
from tests.readium_helpers import fixture_bytes

CLIENT_BOOK_ID = "locator-client-book"
MINIMAL_EPUB = fixture_bytes("minimal")
MINIMAL_EPUB_DIGEST = hashlib.sha256(MINIMAL_EPUB).hexdigest()

# The second of the two identical paragraphs of chapter one: #intro's children
# are h1, p, p, p, p, so it is nth-child(4) rather than nth-child(2).
PLACEABLE_TEXT = "The lantern went out at midnight"
PLACEABLE_START = "/body/DocFragment[1]/body/div/p[3]/text().0"
PLACEABLE_END = "/body/DocFragment[1]/body/div/p[3]/text().32"
PLACEABLE_SELECTOR = "#intro > p:nth-child(4)"

UNPLACEABLE_TEXT = "A passage of a chapter this book does not have"
UNPLACEABLE_START = "/body/DocFragment[9]/body/div/p[1]/text().0"
UNPLACEABLE_END = "/body/DocFragment[9]/body/div/p[1]/text().5"

PAGELESS_TEXT = "Nothing else in the house moved"

# Four ranges spread over both chapters, which one parse of the book covers.
FOUR_PLACEABLE = [
    (PLACEABLE_TEXT, PLACEABLE_START, PLACEABLE_END),
    (
        PAGELESS_TEXT,
        "/body/DocFragment[1]/body/div/p[4]/text().0",
        "/body/DocFragment[1]/body/div/p[4]/text().31",
    ),
    (
        "Morning arrived without ceremony",
        "/body/DocFragment[2]/body/div/p[1]/text().0",
        "/body/DocFragment[2]/body/div/p[1]/text().32",
    ),
    (
        "Chapter Two",
        "/body/DocFragment[2]/body/div/h1/text().0",
        "/body/DocFragment[2]/body/div/h1/text().11",
    ),
]


class _FailingAnchors(XPointCfiPositionAnchorService):
    """An anchor service whose forward conversion raises, as an unreadable archive does."""

    async def locators_for_xpoint_ranges[K: Hashable](
        self, epub_content: bytes, ranges: Mapping[K, XPointRange]
    ) -> dict[K, Locator | None]:
        raise AnchorResolutionError("Cannot read EPUB")


class _CountingAnchors(XPointCfiPositionAnchorService):
    """The real service, counting the forward conversions a sync asks it for."""

    def __init__(self) -> None:
        self.calls = 0

    async def locators_for_xpoint_ranges[K: Hashable](
        self, epub_content: bytes, ranges: Mapping[K, XPointRange]
    ) -> dict[K, Locator | None]:
        self.calls += 1
        return await super().locators_for_xpoint_ranges(epub_content, ranges)


def _overriding_anchors[T](service: T) -> Iterator[T]:
    from src.core import container  # noqa: PLC0415

    container.shared.position_anchor_service.override(service)
    yield service
    container.shared.position_anchor_service.reset_override()


@pytest.fixture
async def ereader_book(db_session: AsyncSession, test_user: models.User) -> models.Book:
    return await create_test_book(
        db_session=db_session,
        user_id=test_user.id,
        title="Placeable Book",
        client_book_id=CLIENT_BOOK_ID,
    )


@pytest.fixture
def broken_anchors() -> Iterator[_FailingAnchors]:
    yield from _overriding_anchors(_FailingAnchors())


@pytest.fixture
def counting_anchors() -> Iterator[_CountingAnchors]:
    yield from _overriding_anchors(_CountingAnchors())


def highlight(text: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
    """One highlight as the plugin sends it, with xpoints only when given both."""
    payload: dict[str, Any] = {"text": text, "page": 1, "datetime": "2024-01-15 14:30:22"}
    if start and end:
        payload["start_xpoint"] = start
        payload["end_xpoint"] = end
    return payload


async def upload_epub(plugin_client: AsyncClient) -> None:
    response = await plugin_client.post(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
        files={"epub": ("book.epub", MINIMAL_EPUB, "application/epub+zip")},
    )
    assert response.status_code == 200, response.text


async def sync(plugin_client: AsyncClient, highlights: list[dict[str, Any]]) -> Response:
    return await plugin_client.post(
        "/api/v1/highlights/sync",
        json={"client_book_id": CLIENT_BOOK_ID, "highlights": highlights},
    )


async def stored(db_session: AsyncSession, text: str) -> models.Highlight:
    db_session.expire_all()
    result = await db_session.execute(select(models.Highlight).filter_by(text=text))
    return result.scalar_one()


async def test_a_synced_highlight_is_placed_against_the_books_epub(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    ereader_book: models.Book,
    storage_dir: Path,
) -> None:
    await upload_epub(plugin_client)

    response = await sync(
        plugin_client, [highlight(PLACEABLE_TEXT, PLACEABLE_START, PLACEABLE_END)]
    )

    assert response.status_code == 200, response.text
    row = await stored(db_session, PLACEABLE_TEXT)
    assert row.locator is not None
    assert row.locator["href"] == "OEBPS/chapter1.xhtml"
    assert row.locator["type"] == "application/xhtml+xml"
    assert row.locator["locations"]["cssSelector"] == PLACEABLE_SELECTOR
    assert 0.0 < row.locator["locations"]["progression"] < 1.0
    assert row.locator["text"]["highlight"] == PLACEABLE_TEXT
    assert row.locator_source_hash == MINIMAL_EPUB_DIGEST


async def test_a_book_with_no_epub_stores_no_locator_and_still_syncs(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    ereader_book: models.Book,
    counting_anchors: _CountingAnchors,
) -> None:
    response = await sync(
        plugin_client, [highlight(PLACEABLE_TEXT, PLACEABLE_START, PLACEABLE_END)]
    )

    assert response.status_code == 200, response.text
    assert counting_anchors.calls == 0
    row = await stored(db_session, PLACEABLE_TEXT)
    assert row.start_xpoint is not None
    assert row.locator is None
    assert row.locator_source_hash is None


async def test_a_sync_parses_the_book_once_for_all_of_its_highlights(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    ereader_book: models.Book,
    storage_dir: Path,
    counting_anchors: _CountingAnchors,
) -> None:
    await upload_epub(plugin_client)

    response = await sync(
        plugin_client, [highlight(text, start, end) for text, start, end in FOUR_PLACEABLE]
    )

    assert response.status_code == 200, response.text
    assert counting_anchors.calls == 1
    for text, _, _ in FOUR_PLACEABLE:
        assert (await stored(db_session, text)).locator is not None


async def test_a_derivation_that_raises_does_not_fail_the_sync(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    ereader_book: models.Book,
    storage_dir: Path,
    broken_anchors: _FailingAnchors,
) -> None:
    await upload_epub(plugin_client)

    response = await sync(
        plugin_client, [highlight(PLACEABLE_TEXT, PLACEABLE_START, PLACEABLE_END)]
    )

    assert response.status_code == 200, response.text
    assert response.json()["highlights_created"] == 1
    row = await stored(db_session, PLACEABLE_TEXT)
    assert row.locator is None


async def test_an_xpointer_this_epub_cannot_place_is_stored_null_against_the_digest(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    ereader_book: models.Book,
    storage_dir: Path,
) -> None:
    await upload_epub(plugin_client)

    response = await sync(
        plugin_client, [highlight(UNPLACEABLE_TEXT, UNPLACEABLE_START, UNPLACEABLE_END)]
    )

    assert response.status_code == 200, response.text
    row = await stored(db_session, UNPLACEABLE_TEXT)
    assert row.locator is None
    assert row.locator_source_hash == MINIMAL_EPUB_DIGEST


async def test_a_highlight_with_no_xpoints_is_never_attempted(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    ereader_book: models.Book,
    storage_dir: Path,
) -> None:
    await upload_epub(plugin_client)

    response = await sync(
        plugin_client,
        [highlight(PLACEABLE_TEXT, PLACEABLE_START, PLACEABLE_END), highlight(PAGELESS_TEXT)],
    )

    assert response.status_code == 200, response.text
    assert (await stored(db_session, PLACEABLE_TEXT)).locator_source_hash == MINIMAL_EPUB_DIGEST
    unplaced = await stored(db_session, PAGELESS_TEXT)
    assert unplaced.locator is None
    assert unplaced.locator_source_hash is None


async def test_a_duplicate_that_gains_xpoints_gains_a_locator_too(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    ereader_book: models.Book,
    storage_dir: Path,
) -> None:
    await create_test_highlight(
        db_session=db_session,
        book=ereader_book,
        user_id=test_user.id,
        text=PLACEABLE_TEXT,
        datetime_str="2024-01-15 14:30:22",
    )
    await upload_epub(plugin_client)

    response = await sync(
        plugin_client, [highlight(PLACEABLE_TEXT, PLACEABLE_START, PLACEABLE_END)]
    )

    assert response.status_code == 200, response.text
    assert response.json()["highlights_created"] == 0
    row = await stored(db_session, PLACEABLE_TEXT)
    assert row.start_xpoint is not None
    assert row.locator is not None
    assert row.locator["locations"]["cssSelector"] == PLACEABLE_SELECTOR
    assert row.locator_source_hash == MINIMAL_EPUB_DIGEST
