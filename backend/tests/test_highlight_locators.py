"""Readium locators derived for a book's highlights (M3.1, #745; M3.2, #746).

Three endpoints, one derivation. ``GET /books/{id}/highlights?include=locator``
places the highlights a *search* matched, ``GET /highlights/{id}/locator``
places one so the reader can jump to it, and
``GET /books/{id}/highlight-locators`` places a whole book's so the reader
can draw every decoration in it.

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

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.common.queries.highlight_row import HighlightRow
from src.application.web_reader.anchors import Locator, LocatorText
from src.application.web_reader.queries.highlight_locators import (
    DerivedHighlightLocator,
    LocatorUnavailable,
)
from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.reading.schemas.highlight_builders import (
    build_highlight_schema,
    resolve_locator,
)
from src.infrastructure.web_reader.schemas.highlight_locator_schemas import HighlightLocator
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
)
from src.models import Book, User
from tests.conftest import create_test_book, create_test_chapter, create_test_highlight
from tests.test_readium_manifest import fixture_bytes, store_epub
from tests.test_readium_session import present, start_publication_session

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


def book_locators_url(book_id: int) -> str:
    return f"/api/v1/books/{book_id}/highlight-locators"


def by_id(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """The book-locators response, keyed by highlight id."""
    return {item["highlight_id"]: item for item in payload["items"]}


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
    epub_content: bytes | None = None,
    delete_file: bool = False,
) -> Book:
    """A book of the fixture EPUB, with one placeable highlight in each chapter.

    Each test gets its own ``epub_filename``. The anchor service caches parsed
    publications by that name for the life of the process, so sharing one across
    tests would let a parse outlive the test that stored it.

    The three ways a book can have no readable EPUB are all reachable from here,
    because they are one answer with three causes: ``with_epub=False`` leaves the
    column null, ``delete_file`` names a file that is not in the store, and
    ``epub_content`` can be bytes that will not parse.
    """
    book = await create_test_book(
        db_session=db_session, user_id=user.id, title="Placed Book", author="A"
    )
    if with_epub:
        await store_epub(
            db_session,
            book,
            storage_dir,
            epub_content if epub_content is not None else fixture_bytes("minimal.epub"),
            filename=epub_filename,
        )
        if delete_file:
            (storage_dir / epub_filename).unlink()
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

    @pytest.mark.parametrize(
        ("cause", "stored"),
        [
            ("no EPUB was ever stored", {"with_epub": False}),
            ("the file is gone from the store", {"delete_file": True}),
            ("what is stored will not parse", {"epub_content": b"not an epub at all"}),
        ],
    )
    async def test_a_book_with_no_readable_epub_says_so_for_every_highlight(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
        cause: str,
        stored: dict[str, Any],
    ) -> None:
        """Three causes, one answer -- and never `unresolved`.

        Each of these highlights has a perfectly good xpointer, and they all
        fail together because the *book* cannot be read. Reporting them as
        `unresolved` would tell a reader their positions were lost when what is
        gone is the file; a book-wide failure has to stay distinguishable from a
        per-highlight one.

        The three are one reason on the wire because a client can do nothing
        different about them: the book cannot be opened in the reader at all.
        Which of the three it was is a matter for the logs, where the difference
        between normal state and data loss is what matters.
        """
        book = await book_with_highlights(
            db_session, test_user, storage_dir, f"unreadable-{len(cause)}.epub", **stored
        )

        response = await client.get(
            highlights_url(book.id), params={"searchText": "o", "include": "locator"}
        )

        assert response.status_code == status.HTTP_200_OK, cause
        placed = by_text(response.json())
        assert len(placed) == 3
        assert all(
            highlight["locator"] == {"locator": None, "unavailable": "no_ebook"}
            for highlight in placed.values()
        ), cause

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


class TestAHighlightDeletedMidResponse:
    """The one shape the API cannot be made to produce, and must still not emit.

    A search response is built from two reads: the view that lists the
    highlights, and the anchor lookup that places them. A DELETE landing between
    the two drops a row from the second, and the highlight would then render
    with a null locator *and* a null reason -- the one combination
    ``HighlightLocator`` documents as impossible, and the one a client written
    against that promise has no branch for.

    The window is too small to open through the API, so the rule is exercised
    where it lives -- beside the schema whose promise it keeps. No mocks: this
    is the real read-model row and the real derived answer the response is built
    from, asserted on the rendered schema rather than on the plumbing.
    """

    def a_row(self, highlight_id: int) -> HighlightRow:
        """One highlight, as the search read model hands it to the builder."""
        moment = datetime(2024, 1, 1, 10, tzinfo=UTC).replace(tzinfo=None)
        return HighlightRow(
            id=highlight_id,
            book_id=1,
            chapter_id=1,
            chapter_name="Chapter One",
            chapter_number=1,
            text=LANTERN,
            page=None,
            datetime=moment,
            label=None,
            removed_from_devices=False,
            tags=(),
            flashcards=(),
            created_at=moment,
            updated_at=moment,
        )

    def rendered(
        self, locators: dict[int, DerivedHighlightLocator], wanted: bool
    ) -> HighlightLocator | None:
        """What the response carries for highlight 7, given what was placed."""
        row = self.a_row(7)
        return build_highlight_schema(row, resolve_locator(row.id, locators, wanted)).locator

    def test_a_highlight_the_anchor_lookup_no_longer_sees_reports_gone(self) -> None:
        locator = self.rendered({}, True)

        assert locator is not None, "a requested locator must never come back as no answer at all"
        assert locator.locator is None
        assert locator.unavailable == LocatorUnavailable.GONE

    def test_without_the_flag_the_same_gap_is_simply_no_locator(self) -> None:
        """Nothing was asked for, so nothing missing is being reported."""
        assert self.rendered({}, False) is None

    def test_a_highlight_the_lookup_did_place_keeps_its_locator(self) -> None:
        """The fill must not swallow the answers that did arrive."""
        placed = DerivedHighlightLocator(
            highlight_id=7,
            locator=Locator(
                href="OEBPS/chapter1.xhtml",
                type="application/xhtml+xml",
                text=LocatorText(highlight=LANTERN),
            ),
        )

        locator = self.rendered({7: placed}, True)

        assert locator is not None
        assert locator.unavailable is None
        assert locator.locator is not None
        assert locator.locator.href == CHAPTER_ONE_HREF
        assert locator.locator.text.highlight == LANTERN


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

    async def test_an_epub_gone_from_the_store_is_no_ebook_here_too(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        book = await book_with_highlights(
            db_session, test_user, storage_dir, "single-vanished.epub", delete_file=True
        )
        chapter = await create_test_chapter(db_session, book, name="Chapter Three")
        orphan = await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="Still perfectly well placed, in a file that is not there.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=LANTERN_XPOINTS[0],
            end_xpoint=LANTERN_XPOINTS[1],
        )

        response = await client.get(locator_url(orphan.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "highlight_id": orphan.id,
            "locator": None,
            "unavailable": "no_ebook",
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


class TestEveryLocatorInABook:
    """``GET /readium/books/{id}/highlight-locators``, the decoration layer's read.

    The reader draws every highlight it can place, so unlike the search view
    above this one is asked for the whole list by construction. What matters
    here is that the list is *complete*: one entry per live highlight, each
    carrying either a place or a reason, so the reader can tell a highlight it
    must not draw from one it was never told about.
    """

    async def test_places_every_live_highlight_in_the_book(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """The whole book, without a search term to narrow it."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "reader-all.epub")

        response = await client.get(book_locators_url(book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        placed = by_id(response.json())
        assert len(placed) == 3
        assert all(item["unavailable"] is None for item in placed.values())
        hrefs = sorted(item["locator"]["href"] for item in placed.values())
        assert hrefs == [CHAPTER_ONE_HREF, CHAPTER_ONE_HREF, CHAPTER_TWO_HREF]
        quoted = {item["locator"]["text"]["highlight"] for item in placed.values()}
        assert quoted == {LANTERN, MORNING, CEREMONY}
        # The sentence occurs twice in chapter one, so the selector is what says
        # which of the two paragraphs this decoration goes on.
        selectors = {item["locator"]["locations"].get("cssSelector") for item in placed.values()}
        assert LANTERN_SELECTOR in selectors
        assert MORNING_SELECTOR in selectors

    async def test_a_whole_book_costs_one_parse(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
        epub_reads: list[str],
    ) -> None:
        """Three highlights in two resources, one EPUB read (ADR-0004 §4)."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "reader-parse.epub")

        response = await client.get(book_locators_url(book.id))

        assert response.status_code == status.HTTP_200_OK
        assert len(by_id(response.json())) == 3
        assert epub_reads.count("reader-parse.epub") == 1

    async def test_each_highlight_reports_its_own_reason(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """One list, four verdicts -- and the placeable ones still place.

        This is what makes the read safe to draw from. A book where some
        highlights are lost is the ordinary case, not an error case, and each
        entry has to say for itself which it is: the reader draws the placed
        ones and M3.4 surfaces the rest.
        """
        book = await book_with_highlights(db_session, test_user, storage_dir, "reader-mixed.epub")
        chapter = await create_test_chapter(db_session, book, name="Chapter One", chapter_number=1)
        elsewhere = await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="Elsewhere entirely.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=XPOINTS_IN_ANOTHER_EDITION[0],
            end_xpoint=XPOINTS_IN_ANOTHER_EDITION[1],
        )
        by_hand = await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="Typed in by hand.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
        )
        stale = await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="A sentence this edition does not contain.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=LANTERN_XPOINTS[0],
            end_xpoint=LANTERN_XPOINTS[1],
        )

        response = await client.get(book_locators_url(book.id))

        assert response.status_code == status.HTTP_200_OK
        placed = by_id(response.json())
        assert len(placed) == 6
        assert placed[elsewhere.id] == {
            "highlight_id": elsewhere.id,
            "locator": None,
            "unavailable": "unresolved",
        }
        assert placed[by_hand.id]["unavailable"] == "not_placeable"
        assert placed[stale.id]["unavailable"] == "text_mismatch"
        drawable = [item for item in placed.values() if item["locator"] is not None]
        assert len(drawable) == 3, "three bad xpointers must not cost the book its decorations"

    async def test_a_book_with_no_readable_epub_says_so_for_every_highlight(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """Never `unresolved`: what is gone is the file, not the reader's positions."""
        book = await book_with_highlights(
            db_session, test_user, storage_dir, "reader-vanished.epub", delete_file=True
        )

        response = await client.get(book_locators_url(book.id))

        assert response.status_code == status.HTTP_200_OK
        assert all(
            item
            == {"highlight_id": item["highlight_id"], "locator": None, "unavailable": "no_ebook"}
            for item in by_id(response.json()).values()
        )

    async def test_a_deleted_highlight_is_simply_absent(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """Nothing to draw and nothing to explain: the reader deleted it."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "reader-deleted.epub")
        chapter = await create_test_chapter(db_session, book, name="Chapter One", chapter_number=1)
        gone = await create_test_highlight(
            db_session,
            book,
            test_user.id,
            text="Struck out.",
            datetime_str=WHEN,
            chapter_id=chapter.id,
            start_xpoint=LANTERN_XPOINTS[0],
            end_xpoint=LANTERN_XPOINTS[1],
            deleted_at=datetime.now(UTC).replace(tzinfo=None),
        )

        response = await client.get(book_locators_url(book.id))

        assert response.status_code == status.HTTP_200_OK
        assert gone.id not in by_id(response.json())

    async def test_a_book_with_no_highlights_answers_an_empty_list(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """An ordinary state of an ordinary book, not a 404 and not a null."""
        await store_epub(
            db_session, test_book, storage_dir, fixture_bytes("minimal.epub"), "reader-bare.epub"
        )

        response = await client.get(book_locators_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"items": []}

    async def test_another_users_book_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        storage_dir: Path,
    ) -> None:
        theirs = await book_with_highlights(
            db_session, other_user, storage_dir, "reader-theirs.epub"
        )

        response = await client.get(book_locators_url(theirs.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_the_publication_cookie_does_not_open_it(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """Should refuse the credential a navigator's iframe carries.

        The route is outside the ``/readium`` prefix on purpose, and this is
        what that buys. Every request the SPA makes for it carries a Bearer
        token -- axios attaches one whenever it holds one and refreshes it on
        401 -- so there is no reachable caller that would be helped by the
        cookie, and accepting it would widen a per-publication credential into
        one that reads a user's highlights.
        """
        book = await book_with_highlights(db_session, test_user, storage_dir, "reader-cookie.epub")
        minted = await start_publication_session(browser_client, test_user, book.id)
        present(browser_client, minted.cookies[PUBLICATION_COOKIE_NAME])

        response = await browser_client.get(book_locators_url(book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_a_bearer_token_opens_it(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """Which is how the SPA asks, every time."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "reader-bearer.epub")

        response = await browser_client.get(
            book_locators_url(book.id),
            headers={"Authorization": f"Bearer {create_access_token(test_user.id)}"},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(by_id(response.json())) == 3

    async def test_a_request_with_no_credential_is_refused(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        book = await book_with_highlights(db_session, test_user, storage_dir, "reader-open.epub")

        response = await browser_client.get(book_locators_url(book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTheSearchViewIsUnchanged:
    """M3.2 added a route; it must not have moved the one M3.1 built."""

    async def test_the_search_endpoint_still_requires_a_search_term(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """The whole-book read lives at its own URL, not behind an optional term."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "still-search.epub")

        response = await client.get(highlights_url(book.id), params={"include": "locator"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_the_search_endpoint_still_places_nothing_without_the_flag(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
        epub_reads: list[str],
    ) -> None:
        """The flag still gates the parse, and the new route does not gate itself."""
        book = await book_with_highlights(db_session, test_user, storage_dir, "still-flagged.epub")

        response = await client.get(highlights_url(book.id), params={"searchText": "the"})

        assert response.status_code == status.HTTP_200_OK
        assert all(highlight["locator"] is None for highlight in by_text(response.json()).values())
        assert "still-flagged.epub" not in epub_reads
