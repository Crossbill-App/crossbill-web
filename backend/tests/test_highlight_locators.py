"""Readium locators derived for a book's highlights (M3.1, #745).

Two endpoints, one derivation. ``GET /books/{id}/highlights?include=locator``
places a whole book's highlights so the reader can draw them, and
``GET /highlights/{id}/locator`` places one so the reader can jump to it.

Every locator here is converted for real against ``tests/fixtures/minimal.epub``
-- no anchor service is faked -- because what is under test is not that a field
appears but that the thing in it is *right*, and ADR-0004 §5 makes "right" mean
"the derived anchor covers the text that was stored". The fixture is built for
that: chapter one repeats one sentence in two paragraphs, so a highlight can be
put somewhere a lazy conversion would get wrong.

The failure cases matter as much as the happy one. A highlight whose EPUB has
been replaced must come back as a *reason*, not as a confident wrong place and
not as a 500, because the canonical xpointer is safely stored either way and
only this view of it is lost.
"""

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.library.repositories.file_repository import FileRepository
from src.models import Book, User
from tests.conftest import create_test_book, create_test_chapter, create_test_highlight
from tests.test_readium_manifest import fixture_bytes, store_epub

# Paragraphs of the fixture, and the xpointer range KOReader would have stored
# for a highlight covering each. The offsets are character counts into the
# paragraph's text node, which is what crengine writes and what the conversion
# reads back out of the document.
LANTERN = "The lantern went out at midnight."
LANTERN_XPOINTS = (
    "/body/DocFragment[1]/body/div[1]/p[1]/text().0",
    "/body/DocFragment[1]/body/div[1]/p[1]/text().33",
)
LANTERN_SELECTOR = "#intro > p:nth-child(2)"

# The last paragraph of chapter one. Occurs once, unlike the sentence above,
# which occurs twice -- so the two together prove the conversion is placing a
# highlight rather than finding the first paragraph that looks like it.
MORNING = "Nothing else in the house moved until morning."
MORNING_XPOINTS = (
    "/body/DocFragment[1]/body/div[1]/p[4]/text().0",
    "/body/DocFragment[1]/body/div[1]/p[4]/text().46",
)
MORNING_SELECTOR = "#intro > p:nth-child(5)"

# The first paragraph of chapter two: a second resource, so a book's highlights
# are not all in one document.
CEREMONY = "Morning arrived without ceremony."
CEREMONY_XPOINTS = (
    "/body/DocFragment[2]/body/div[1]/p[1]/text().0",
    "/body/DocFragment[2]/body/div[1]/p[1]/text().33",
)

CHAPTER_ONE_HREF = "resources/OEBPS/chapter1.xhtml"
CHAPTER_TWO_HREF = "resources/OEBPS/chapter2.xhtml"

# An xpointer into a fifth spine document, which the fixture does not have. The
# shape a replaced EPUB takes for a highlight that can no longer be placed.
XPOINTS_IN_ANOTHER_EDITION = (
    "/body/DocFragment[5]/body/div[1]/p[1]/text().0",
    "/body/DocFragment[5]/body/div[1]/p[1]/text().10",
)

WHEN = "2024-01-01 10:00:00"


def highlights_url(book_id: int) -> str:
    return f"/api/v1/books/{book_id}/highlights"


def locator_url(highlight_id: int) -> str:
    return f"/api/v1/highlights/{highlight_id}/locator"


def by_text(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The response's highlights, keyed by their text, across every chapter."""
    return {
        highlight["text"]: highlight
        for chapter in payload["chapters"]
        for highlight in chapter["highlights"]
    }


@pytest.fixture
def epub_reads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Records every EPUB the file store is asked for, by filename.

    Patched on the class rather than on an instance because the anchor service
    is a DI singleton built once for the process: it holds whichever file
    repository it was constructed with, which is not necessarily the one this
    test's client installed.
    """
    reads: list[str] = []
    original = FileRepository.get_epub

    async def recording(self: FileRepository, filename: str) -> bytes | None:
        reads.append(filename)
        return await original(self, filename)

    monkeypatch.setattr(FileRepository, "get_epub", recording)
    return reads


async def book_with_highlights(
    db_session: AsyncSession,
    user: User,
    storage_dir: Path,
    epub_filename: str,
    *,
    with_epub: bool = True,
) -> Book:
    """A book of the fixture EPUB, with one placeable highlight in each chapter.

    Each test gets its own ``epub_filename``. The anchor service caches parsed
    publications by that name for the life of the process, so sharing one across
    tests would let a parse outlive the test that stored it.
    """
    book = await create_test_book(
        db_session=db_session, user_id=user.id, title="Placed Book", author="A"
    )
    if with_epub:
        await store_epub(
            db_session, book, storage_dir, fixture_bytes("minimal.epub"), filename=epub_filename
        )
    one = await create_test_chapter(db_session, book, name="Chapter One", chapter_number=1)
    two = await create_test_chapter(db_session, book, name="Chapter Two", chapter_number=2)
    await create_test_highlight(
        db_session,
        book,
        user.id,
        text=LANTERN,
        datetime_str=WHEN,
        chapter_id=one.id,
        start_xpoint=LANTERN_XPOINTS[0],
        end_xpoint=LANTERN_XPOINTS[1],
    )
    await create_test_highlight(
        db_session,
        book,
        user.id,
        text=MORNING,
        datetime_str=WHEN,
        chapter_id=one.id,
        start_xpoint=MORNING_XPOINTS[0],
        end_xpoint=MORNING_XPOINTS[1],
    )
    await create_test_highlight(
        db_session,
        book,
        user.id,
        text=CEREMONY,
        datetime_str=WHEN,
        chapter_id=two.id,
        start_xpoint=CEREMONY_XPOINTS[0],
        end_xpoint=CEREMONY_XPOINTS[1],
    )
    return book


class TestLocatorsForABooksHighlights:
    """``?include=locator`` on the book's highlight view."""

    async def test_places_every_highlight_in_the_resource_it_belongs_to(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        book = await book_with_highlights(db_session, test_user, storage_dir, "placed-all.epub")

        response = await client.get(
            highlights_url(book.id), params={"searchText": "the", "include": "locator"}
        )

        assert response.status_code == status.HTTP_200_OK
        found = by_text(response.json())
        lantern = found[LANTERN]["locator"]
        assert lantern["unavailable"] is None
        assert lantern["locator"]["href"] == CHAPTER_ONE_HREF
        assert lantern["locator"]["text"]["highlight"] == LANTERN
        # The sentence occurs twice in this chapter, so the selector is what
        # says which of the two this highlight is on.
        assert lantern["locator"]["locations"]["cssSelector"] == LANTERN_SELECTOR

        morning = found[MORNING]["locator"]
        assert morning["locator"]["locations"]["cssSelector"] == MORNING_SELECTOR
        assert morning["locator"]["text"]["highlight"] == MORNING

    async def test_places_a_highlight_in_the_second_resource(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """A book's highlights are not all in one document, and the href says so."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "placed-two.epub")

        response = await client.get(
            highlights_url(book.id), params={"searchText": "ceremony", "include": "locator"}
        )

        ceremony = by_text(response.json())[CEREMONY]["locator"]
        assert ceremony["locator"]["href"] == CHAPTER_TWO_HREF
        assert ceremony["locator"]["text"]["highlight"] == CEREMONY

    async def test_a_whole_book_costs_one_parse(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
        epub_reads: list[str],
    ) -> None:
        """Three highlights in two resources, one EPUB read (ADR-0004 §4).

        The filename is unique to this test, so the anchor service's cache is
        cold for it and every read it does is counted here. What this pins down
        is the shape the measurement in §4 assumes: converting a book's whole
        highlight list fetches and parses the publication once, not once per
        highlight.
        """
        book = await book_with_highlights(db_session, test_user, storage_dir, "one-parse.epub")

        # A letter every one of the three paragraphs contains, so the search
        # returns the whole book rather than a subset of it.
        response = await client.get(
            highlights_url(book.id), params={"searchText": "o", "include": "locator"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(by_text(response.json())) == 3
        assert epub_reads.count("one-parse.epub") == 1

    async def test_without_the_flag_there_is_no_locator_and_no_epub_is_read(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
        epub_reads: list[str],
    ) -> None:
        """The flag is what gates the parse, which is the whole point of it being one."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "unread.epub")

        response = await client.get(highlights_url(book.id), params={"searchText": "the"})

        assert response.status_code == status.HTTP_200_OK
        found = by_text(response.json())
        assert found
        assert all(highlight["locator"] is None for highlight in found.values())
        assert "unread.epub" not in epub_reads

    async def test_a_highlight_whose_text_no_longer_matches_is_withheld(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """The replaced-edition case: a locator resolved, onto the wrong words.

        This is the failure ADR-0004 §5 exists for. The conversion succeeds --
        the xpointer names a paragraph the book has -- and the paragraph says
        something else, which without verification would be a highlight drawn
        confidently in the wrong place.
        """
        book = await book_with_highlights(db_session, test_user, storage_dir, "mismatch.epub")
        chapter = await create_test_chapter(db_session, book, name="Chapter One", chapter_number=1)
        await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="A sentence this edition does not contain.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=LANTERN_XPOINTS[0],
            end_xpoint=LANTERN_XPOINTS[1],
        )

        response = await client.get(
            highlights_url(book.id), params={"searchText": "edition", "include": "locator"}
        )

        stale = by_text(response.json())["A sentence this edition does not contain."]["locator"]
        assert stale["locator"] is None
        assert stale["unavailable"] == "text_mismatch"

    async def test_a_highlight_pointing_outside_the_book_is_unresolved(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """A range naming a spine document this EPUB has not got."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "unresolved.epub")
        chapter = await create_test_chapter(db_session, book, name="Chapter One", chapter_number=1)
        await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="Elsewhere entirely.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=XPOINTS_IN_ANOTHER_EDITION[0],
            end_xpoint=XPOINTS_IN_ANOTHER_EDITION[1],
        )

        response = await client.get(
            highlights_url(book.id), params={"searchText": "Elsewhere", "include": "locator"}
        )

        lost = by_text(response.json())["Elsewhere entirely."]["locator"]
        assert lost["locator"] is None
        assert lost["unavailable"] == "unresolved"
        # The rest of the book still places: one bad xpointer is one missing
        # view, not a failed request.
        placed = await client.get(
            highlights_url(book.id), params={"searchText": "lantern", "include": "locator"}
        )
        assert by_text(placed.json())[LANTERN]["locator"]["locator"] is not None

    async def test_a_highlight_that_was_never_placed_says_so(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """Highlights synced without xpointers are real highlights that are nowhere."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "unplaceable.epub")
        chapter = await create_test_chapter(db_session, book, name="Chapter One", chapter_number=1)
        await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="Typed in by hand.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
        )

        response = await client.get(
            highlights_url(book.id), params={"searchText": "Typed", "include": "locator"}
        )

        loose = by_text(response.json())["Typed in by hand."]["locator"]
        assert loose["locator"] is None
        assert loose["unavailable"] == "not_placeable"

    async def test_a_book_with_no_epub_says_so_rather_than_failing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        book = await book_with_highlights(
            db_session, test_user, storage_dir, "absent.epub", with_epub=False
        )

        response = await client.get(
            highlights_url(book.id), params={"searchText": "lantern", "include": "locator"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert by_text(response.json())[LANTERN]["locator"]["unavailable"] == "no_ebook"

    async def test_another_users_book_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        storage_dir: Path,
    ) -> None:
        theirs = await book_with_highlights(db_session, other_user, storage_dir, "theirs.epub")

        response = await client.get(
            highlights_url(theirs.id), params={"searchText": "lantern", "include": "locator"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestOneHighlightsLocator:
    """``GET /highlights/{id}/locator``, the jump M3.3 makes."""

    async def test_places_the_highlight(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        book = await book_with_highlights(db_session, test_user, storage_dir, "single.epub")
        listed = await client.get(
            highlights_url(book.id), params={"searchText": "morning", "include": "locator"}
        )
        highlight_id = by_text(listed.json())[MORNING]["id"]

        response = await client.get(locator_url(highlight_id))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["highlight_id"] == highlight_id
        assert body["unavailable"] is None
        assert body["locator"]["href"] == CHAPTER_ONE_HREF
        assert body["locator"]["text"]["highlight"] == MORNING
        assert body["locator"]["locations"]["cssSelector"] == MORNING_SELECTOR

    async def test_a_highlight_that_cannot_be_placed_answers_a_reason(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """200 with a reason, not 404: the highlight is there, its place is not."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "single-lost.epub")
        chapter = await create_test_chapter(db_session, book, name="Chapter One", chapter_number=1)
        lost = await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="Elsewhere entirely.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=XPOINTS_IN_ANOTHER_EDITION[0],
            end_xpoint=XPOINTS_IN_ANOTHER_EDITION[1],
        )

        response = await client.get(locator_url(lost.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "highlight_id": lost.id,
            "locator": None,
            "unavailable": "unresolved",
        }

    async def test_an_unknown_highlight_is_not_found(self, client: AsyncClient) -> None:
        response = await client.get(locator_url(999_999))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_another_users_highlight_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        storage_dir: Path,
    ) -> None:
        theirs = await book_with_highlights(
            db_session, other_user, storage_dir, "theirs-single.epub"
        )
        chapter = await create_test_chapter(db_session, theirs, name="Chapter One")
        hidden = await create_test_highlight(
            db_session,
            theirs,
            other_user.id,
            text="Their own marked passage.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=LANTERN_XPOINTS[0],
            end_xpoint=LANTERN_XPOINTS[1],
        )

        response = await client.get(locator_url(hidden.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_a_deleted_highlight_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_book: Book,
    ) -> None:
        from datetime import UTC, datetime  # noqa: PLC0415

        gone = await create_test_highlight(
            db_session,
            test_book,
            test_user.id,
            text=LANTERN,
            datetime_str=WHEN,
            deleted_at=datetime.now(UTC).replace(tzinfo=None),
        )

        response = await client.get(locator_url(gone.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND
