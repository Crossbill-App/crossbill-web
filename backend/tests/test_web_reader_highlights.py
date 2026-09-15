"""Making a highlight by selecting text in the browser (M4.2, #751).

``minimal.epub`` throughout, as the reading-position tests use it: each chapter
holds one sentence that occurs nowhere else in the book, and chapter one holds
the same sentence twice, which is what makes an ambiguous quote observable.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.application.web_reader.anchors import AnchorConfidence
from src.domain.common.devices import WEB_READER_DEVICE_ID
from tests.conftest import create_test_book, create_test_highlight, create_test_highlight_style
from tests.readium_helpers import another_users_book, fixture_bytes
from tests.test_readium_manifest import store_epub

CH1_HREF = "resources/OEBPS/chapter1.xhtml"
CH2_HREF = "resources/OEBPS/chapter2.xhtml"
MEDIA_TYPE = "application/xhtml+xml"

# One sentence per chapter that occurs nowhere else, and where each one sits.
CH1_QUOTE = "Nothing else in the house moved"
CH1_START_XPOINT = "/body/DocFragment[1]/body/div[1]/p[4]"
CH2_QUOTE = "Morning arrived without ceremony"
CH2_START_XPOINT = "/body/DocFragment[2]/body/div[1]/p[1]"
THE_SAME_TWICE = "The lantern went out at midnight"
# What runs into chapter one's second copy of that sentence, and so tells it from the first.
BEFORE_THE_SECOND = "She wrote the same sentence twice, and meant it both times."
SECOND_COPY_XPOINT = "/body/DocFragment[1]/body/div[1]/p[3]"
# What surrounds chapter one's unique sentence, as a navigator sends a selection.
BEFORE_CH1_QUOTE = "The lantern went out at midnight."
AFTER_CH1_QUOTE = " until morning."

# Chapter one's quote resolves to position 10 and chapter two's to 16, with chapter
# two's heading at 15 -- so a chapter boundary drawn at 15 puts one on each side.
CHAPTER_TWO_STARTS_AT = [15, 0]

# When a highlight this test deletes was deleted; only that it is set matters.
DELETED_AT = datetime(2026, 2, 1, tzinfo=UTC)


def url(book_id: int) -> str:
    return f"/api/v1/books/{book_id}/highlights"


def selection(
    href: str = CH1_HREF,
    quote: str | None = CH1_QUOTE,
    before: str | None = None,
    after: str | None = None,
    selector: str | None = None,
) -> dict[str, Any]:
    """One Readium Locator as a navigator hands over a selection."""
    text: dict[str, str] = {}
    if before is not None:
        text["before"] = before
    if quote is not None:
        text["highlight"] = quote
    if after is not None:
        text["after"] = after
    locations = {"cssSelector": selector} if selector else {}
    return {"href": href, "type": MEDIA_TYPE, "locations": locations, "text": text}


async def post(
    client: AsyncClient,
    book: models.Book,
    locator: dict[str, Any] | None = None,
    note: str | None = None,
    highlight_style_id: int | None = None,
) -> Response:
    return await client.post(
        url(book.id),
        json={
            "locator": locator if locator is not None else selection(),
            "note": note,
            "highlight_style_id": highlight_style_id,
        },
    )


async def created(
    client: AsyncClient,
    book: models.Book,
    locator: dict[str, Any] | None = None,
    note: str | None = None,
    highlight_style_id: int | None = None,
) -> dict[str, Any]:
    response = await post(client, book, locator, note, highlight_style_id)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def stored_highlights(db_session: AsyncSession, book: models.Book) -> list[models.Highlight]:
    rows = await db_session.execute(
        select(models.Highlight)
        .filter_by(book_id=book.id)
        .order_by(models.Highlight.id)
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().all())


@pytest.fixture
async def readable_book(
    db_session: AsyncSession, test_book: models.Book, storage_dir: Path
) -> models.Book:
    """The user's own book, with ``minimal.epub`` on disk to place a selection in."""
    await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal"))
    return test_book


@pytest.fixture
async def chaptered_book(db_session: AsyncSession, readable_book: models.Book) -> models.Book:
    """The same book with its two chapters placed, so selections can be attributed."""
    db_session.add_all(
        [
            models.Chapter(
                book_id=readable_book.id,
                name="One",
                chapter_number=1,
                start_position=[1, 0],
                end_position=CHAPTER_TWO_STARTS_AT,
            ),
            models.Chapter(
                book_id=readable_book.id,
                name="Two",
                chapter_number=2,
                start_position=CHAPTER_TWO_STARTS_AT,
                end_position=None,
            ),
        ]
    )
    await db_session.commit()
    return readable_book


async def test_a_selection_is_stored_as_a_highlight_the_e_reader_will_recognise(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    body = await created(client, readable_book)

    assert body["text"] == CH1_QUOTE
    assert body["start_xpoint"] == CH1_START_XPOINT
    assert body["end_xpoint"].startswith(CH1_START_XPOINT)

    rows = await stored_highlights(db_session, readable_book)
    assert len(rows) == 1
    assert rows[0].id == body["id"]
    assert rows[0].text == CH1_QUOTE
    assert rows[0].start_xpoint == CH1_START_XPOINT
    assert rows[0].position == [10, 0]
    assert rows[0].origin_device_id == WEB_READER_DEVICE_ID
    # The device's own convention: a wall clock carrying no offset to place it at.
    assert rows[0].datetime.tzinfo is None


async def test_the_selection_locator_is_stored_with_the_grade_it_resolved_at(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    await created(
        client,
        readable_book,
        selection(
            quote=CH1_QUOTE,
            before=BEFORE_CH1_QUOTE,
            after=AFTER_CH1_QUOTE,
            selector="#intro > p:nth-child(5)",
        ),
    )

    row = (await stored_highlights(db_session, readable_book))[0]
    # In the EPUB's own coordinates, as every other stored locator is.
    assert row.locator is not None
    assert row.locator["href"] == "OEBPS/chapter1.xhtml"
    assert row.locator["text"]["highlight"] == CH1_QUOTE
    assert row.locator["locations"]["cssSelector"] == "#intro > p:nth-child(5)"
    assert row.locator_source_hash
    # The reverse direction is the only one that grades a locator at all.
    assert row.locator_confidence == AnchorConfidence.BOTH_CONTEXTS


async def test_a_selection_is_attributed_to_the_chapter_whose_range_holds_it(
    client: AsyncClient, db_session: AsyncSession, chaptered_book: models.Book
) -> None:
    first = await created(client, chaptered_book, selection(CH1_HREF, CH1_QUOTE))
    second = await created(client, chaptered_book, selection(CH2_HREF, CH2_QUOTE))

    chapters = {row.name: row.id for row in await db_session.scalars(select(models.Chapter))}
    assert first["chapter_id"] == chapters["One"]
    assert second["chapter_id"] == chapters["Two"]


async def test_a_book_whose_chapters_are_unplaced_attributes_nothing(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    db_session.add(models.Chapter(book_id=readable_book.id, name="Unplaced", chapter_number=1))
    await db_session.commit()

    assert (await created(client, readable_book))["chapter_id"] is None


async def test_a_note_and_a_label_are_stored_with_the_highlight(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    readable_book: models.Book,
) -> None:
    style = await create_test_highlight_style(
        db_session, user_id=test_user.id, book_id=readable_book.id, label="Important"
    )

    body = await created(
        client, readable_book, note="Worth coming back to", highlight_style_id=style.id
    )

    assert body["note"] == "Worth coming back to"
    assert body["highlight_style_id"] == style.id
    row = (await stored_highlights(db_session, readable_book))[0]
    assert row.koreader_note == "Worth coming back to"
    assert row.highlight_style_id == style.id


async def test_another_books_label_is_not_one_this_book_can_be_filed_under(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    readable_book: models.Book,
) -> None:
    elsewhere = await create_test_book(db_session, user_id=test_user.id, title="Elsewhere")
    style = await create_test_highlight_style(
        db_session, user_id=test_user.id, book_id=elsewhere.id, label="Theirs"
    )

    response = await post(client, readable_book, highlight_style_id=style.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert await stored_highlights(db_session, readable_book) == []


async def test_the_same_passage_marked_twice_stays_one_highlight(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    first = await created(client, readable_book)

    response = await post(client, readable_book)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["id"] == first["id"]
    assert len(await stored_highlights(db_session, readable_book)) == 1


async def test_marking_a_passage_again_brings_back_the_highlight_that_was_deleted(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    readable_book: models.Book,
) -> None:
    # A deleted row cannot be replaced by a second one -- the content hash is unique
    # per book -- so a deliberate re-selection brings the stored one back, as a
    # KOReader push flagged new on its device does.
    gone = await create_test_highlight(
        db_session,
        book=readable_book,
        user_id=test_user.id,
        text=CH1_QUOTE,
        datetime_str="2026-01-01 10:00:00",
        deleted_at=DELETED_AT,
        removed_from_devices_at=DELETED_AT,
    )

    response = await post(client, readable_book)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["id"] == gone.id
    rows = await stored_highlights(db_session, readable_book)
    assert len(rows) == 1
    assert rows[0].deleted_at is None
    assert rows[0].removed_from_devices_at is None


async def test_a_quote_the_book_holds_twice_is_too_weak_to_store(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    response = await post(client, readable_book, selection(CH1_HREF, THE_SAME_TWICE))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert await stored_highlights(db_session, readable_book) == []


async def test_a_quote_the_book_holds_twice_is_stored_once_its_context_settles_it(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    """The context is what a selection carries and an ambiguous quote alone does not."""
    ambiguous = await post(client, readable_book, selection(CH1_HREF, THE_SAME_TWICE))
    assert ambiguous.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    body = await created(
        client, readable_book, selection(CH1_HREF, THE_SAME_TWICE, before=BEFORE_THE_SECOND)
    )

    assert body["text"] == THE_SAME_TWICE
    assert body["start_xpoint"] == SECOND_COPY_XPOINT
    assert len(await stored_highlights(db_session, readable_book)) == 1


async def test_text_the_book_does_not_hold_is_refused(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    response = await post(client, readable_book, selection(CH1_HREF, "Words from another book"))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert await stored_highlights(db_session, readable_book) == []


@pytest.mark.parametrize("quote", ["", "   ", None])
async def test_a_selection_quoting_nothing_is_not_a_highlight(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book, quote: str | None
) -> None:
    response = await post(client, readable_book, selection(CH1_HREF, quote))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert await stored_highlights(db_session, readable_book) == []


async def test_surrounding_whitespace_is_not_part_of_what_was_selected(
    client: AsyncClient, db_session: AsyncSession, readable_book: models.Book
) -> None:
    body = await created(client, readable_book, selection(CH1_HREF, f"\n  {CH1_QUOTE}  \n"))

    assert body["text"] == CH1_QUOTE
    # The same passage selected tidily is the same highlight, not a second row.
    assert (await post(client, readable_book)).status_code == status.HTTP_200_OK
    assert len(await stored_highlights(db_session, readable_book)) == 1


async def test_a_book_whose_file_cannot_be_read_is_answered_apart_from_a_bad_selection(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: models.User,
    storage_dir: Path,
) -> None:
    book = await create_test_book(db_session=db_session, user_id=test_user.id, title="Corrupt")
    await store_epub(db_session, book, storage_dir, b"not an archive at all", "corrupt.epub")

    response = await post(client, book)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text
    assert await stored_highlights(db_session, book) == []


async def test_a_book_with_no_epub_is_not_found(
    client: AsyncClient, test_book: models.Book
) -> None:
    response = await post(client, test_book)

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_another_users_book_is_not_found(
    client: AsyncClient, db_session: AsyncSession, storage_dir: Path
) -> None:
    theirs = await another_users_book(db_session)
    await store_epub(db_session, theirs, storage_dir, fixture_bytes("minimal"), "theirs.epub")

    response = await post(client, theirs)

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert await stored_highlights(db_session, theirs) == []
