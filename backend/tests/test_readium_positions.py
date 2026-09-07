"""Tests for the position list a publication's manifest links to.

A *position* is Readium's synthetic page: a reflowable EPUB has no pages of its
own, so the reading order is cut into 1024-byte pieces and each piece gets a
Locator. The numbers are a convention, and a convention is only worth anything
if everyone computes it identically -- so the assertions here are exact values
rather than shapes, because "some monotone sequence" would pass for a numbering
no other Readium implementation would reproduce.

The sizes the cut is made on are each archive member's *uncompressed* length as
the central directory declares it, so a position list decompresses nothing.
Hand-built EPUBs are what make that observable: their members' bytes are written
out here, so a count asserted below is a division a reader can do on the page.
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urljoin

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.main import app
from src.models import Book, User
from tests.conftest import create_test_book
from tests.test_readium_manifest import (
    POSITION_LIST_MEDIA_TYPE,
    POSITION_LIST_REL,
    build_epub,
    fixture_bytes,
    manifest_url,
    store_epub,
)


def positions_url(book: Book) -> str:
    return f"/api/v1/readium/books/{book.id}/positions.json"


# Two reflowable chapters whose sizes straddle the 1024-byte cut: the first is
# exactly two positions' worth, the second is one byte over one position's, so a
# count that truncated instead of rounding up would lose the last byte of the
# book. Both counts are powers of two, so every progression below is an exact
# binary fraction and can be asserted as a literal.
TWO_LONG_CHAPTERS_EPUB = build_epub(
    manifest_items=(
        '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="c2" href="c2.xhtml" media-type="application/xhtml+xml"/>'
    ),
    spine='<itemref idref="c1"/><itemref idref="c2"/>',
    nav_links='<li><a href="c1.xhtml">One</a></li><li><a href="c2.xhtml">Two</a></li>',
    files=("c1.xhtml", "c2.xhtml"),
    bodies={"c1.xhtml": b"a" * 2048, "c2.xhtml": b"b" * 1025},
)

# The same two documents, four positions' worth of bytes each, in a publication
# the author typeset as fixed-layout pages. Sized so that the layout is what
# decides the count and not the file: cut reflowably these would be eight
# positions, not two.
FIXED_LAYOUT_PAGES_EPUB = build_epub(
    manifest_items=(
        '<item id="p1" href="p1.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="p2" href="p2.xhtml" media-type="application/xhtml+xml"/>'
    ),
    spine='<itemref idref="p1"/><itemref idref="p2"/>',
    nav_links='<li><a href="p1.xhtml">One</a></li><li><a href="p2.xhtml">Two</a></li>',
    files=("p1.xhtml", "p2.xhtml"),
    bodies={"p1.xhtml": b"a" * 4096, "p2.xhtml": b"b" * 4096},
    extra_metadata='<meta property="rendition:layout">pre-paginated</meta>',
)


@pytest.fixture
async def anonymous_client() -> AsyncGenerator[AsyncClient, None]:
    """A client with no authentication override, to see what the endpoint demands."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as unauthenticated:
        yield unauthenticated


@pytest.fixture
async def long_chapters_book(db_session: AsyncSession, test_book: Book, storage_dir: Path) -> Book:
    """A book whose two chapters are worth two positions each."""
    await store_epub(db_session, test_book, storage_dir, TWO_LONG_CHAPTERS_EPUB)
    return test_book


class TestThePositionList:
    """What GET /api/v1/readium/books/{id}/positions.json contains."""

    async def test_gives_a_short_chapter_one_position_each(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should number two sub-kilobyte chapters as two positions, start to start.

        ``minimal.epub``'s chapters are 447 and 336 bytes, so each is worth one
        position and the whole book is worth two: the first begins the book, the
        second is halfway through it.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(positions_url(test_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"].startswith(POSITION_LIST_MEDIA_TYPE)
        assert response.json() == {
            "total": 2,
            "positions": [
                {
                    "href": "resources/OEBPS/chapter1.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 1, "progression": 0.0, "totalProgression": 0.0},
                },
                {
                    "href": "resources/OEBPS/chapter2.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 2, "progression": 0.0, "totalProgression": 0.5},
                },
            ],
        }

    async def test_cuts_a_long_chapter_into_a_position_per_kilobyte(
        self, client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should give a 2048-byte chapter two positions and a 1025-byte one two as well.

        The second chapter is what pins the rounding: one byte past a kilobyte
        is a second position, because the alternative is a tail of the book no
        position names.
        """
        response = await client.get(positions_url(long_chapters_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == {
            "total": 4,
            "positions": [
                {
                    "href": "resources/c1.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 1, "progression": 0.0, "totalProgression": 0.0},
                },
                {
                    "href": "resources/c1.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 2, "progression": 0.5, "totalProgression": 0.25},
                },
                {
                    "href": "resources/c2.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 3, "progression": 0.0, "totalProgression": 0.5},
                },
                {
                    "href": "resources/c2.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 4, "progression": 0.5, "totalProgression": 0.75},
                },
            ],
        }

    async def test_total_counts_the_positions_listed(
        self, client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should not state a total the list does not hold.

        A reader shows "page n of total" from these two numbers separately, so a
        total that outran the array would number pages it could never reach.
        """
        document = (await client.get(positions_url(long_chapters_book))).json()

        assert document["total"] == len(document["positions"]) == 4

    async def test_numbers_positions_from_one_without_a_gap(
        self, client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should count across the whole publication, not restart at each resource.

        A position is the unit a reader stores as "where I was", so a numbering
        that restarted per resource would give one book several position 1s.
        """
        document = (await client.get(positions_url(long_chapters_book))).json()

        numbers = [position["locations"]["position"] for position in document["positions"]]
        assert numbers == list(range(1, document["total"] + 1))

    async def test_total_progression_rises_with_the_position(
        self, client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should place every position further into the book than the one before."""
        document = (await client.get(positions_url(long_chapters_book))).json()

        progressions = [
            position["locations"]["totalProgression"] for position in document["positions"]
        ]
        assert progressions[0] == 0.0
        assert progressions == sorted(progressions)
        assert len(set(progressions)) == len(progressions)
        assert max(progressions) < 1.0

    async def test_a_fixed_layout_page_is_one_position_however_long(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should give a pre-paginated publication one position per page.

        Both documents run to 4096 bytes, so cutting them by size would make
        eight positions out of a two-page book -- numbering seven places inside
        pages the reader displays whole.
        """
        await store_epub(db_session, test_book, storage_dir, FIXED_LAYOUT_PAGES_EPUB)

        response = await client.get(positions_url(test_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == {
            "total": 2,
            "positions": [
                {
                    "href": "resources/p1.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 1, "progression": 0.0, "totalProgression": 0.0},
                },
                {
                    "href": "resources/p2.xhtml",
                    "type": "application/xhtml+xml",
                    "locations": {"position": 2, "progression": 0.0, "totalProgression": 0.5},
                },
            ],
        }

    async def test_a_spine_item_overridden_to_fixed_is_still_one_position(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should read the layout per reading-order item, as the manifest does.

        ``fixed_layout.epub`` states one layout for the publication and
        overrides it on one spine item, so its two pages are laid out
        differently and both are small enough to be one position either way --
        which is exactly why this asserts the hrefs rather than only a count.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("fixed_layout.epub"))

        response = await client.get(positions_url(test_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        document = response.json()
        assert document["total"] == 2
        assert [position["href"] for position in document["positions"]] == [
            "resources/page1.xhtml",
            "resources/page2.xhtml",
        ]

    async def test_only_the_reading_order_gets_positions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should not number a stylesheet, an image or the navigation document.

        None of them is a place a reader can be, and counting them would push
        every real position's number and progression off by the size of the
        book's assets.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("nested_toc.epub"))

        document = (await client.get(positions_url(test_book))).json()

        assert [position["href"] for position in document["positions"]] == [
            "resources/EPUB/text/chapter%201.xhtml",
            "resources/EPUB/text/luku-%C3%A4%C3%A4ni.xhtml",
        ]


class TestThePositionListIsReachedFromTheManifest:
    """The link is the contract: a reader only ever gets here by following it."""

    async def test_the_manifests_position_list_link_resolves(
        self, client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should serve the position list at the href the manifest advertises.

        The href is relative, so a navigator resolves it against the manifest's
        own URL -- and that resolution is what is followed here, rather than a
        path copied out of the router.
        """
        manifest_response = await client.get(manifest_url(long_chapters_book))
        link = next(
            link for link in manifest_response.json()["links"] if link["rel"] == POSITION_LIST_REL
        )

        resolved = urljoin(str(manifest_response.url), link["href"])
        response = await client.get(resolved)

        assert response.status_code == status.HTTP_200_OK, resolved
        assert response.headers["content-type"].startswith(link["type"])
        assert response.json()["total"] == 4

    async def test_every_position_names_a_servable_resource(
        self, client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should give each position an href the resource endpoint will serve.

        A locator pointing at a file the reader cannot fetch is the failure the
        two endpoints can only have together, so the position list drives the
        requests rather than a list written out here.
        """
        document = (await client.get(positions_url(long_chapters_book))).json()
        hrefs = {position["href"] for position in document["positions"]}
        assert len(hrefs) == 2

        for href in hrefs:
            response = await client.get(f"/api/v1/readium/books/{long_chapters_book.id}/{href}")

            assert response.status_code == status.HTTP_200_OK, href
            assert response.content, href


class TestPositionListAccess:
    """Who may read a book's positions, and what happens when there is no book."""

    async def test_requires_authentication(
        self, anonymous_client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should reject an unauthenticated request rather than describe the book."""
        response = await anonymous_client.get(positions_url(long_chapters_book))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_another_users_book_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        storage_dir: Path,
    ) -> None:
        """Should answer 404 for a readable publication belonging to somebody else."""
        their_book = await create_test_book(
            db_session=db_session, user_id=other_user.id, title="Not Yours"
        )
        await store_epub(db_session, their_book, storage_dir, TWO_LONG_CHAPTERS_EPUB)

        response = await client.get(positions_url(their_book))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "positions" not in response.text

    async def test_unknown_book_is_not_found(self, client: AsyncClient) -> None:
        """Should answer 404 for a book id that exists for nobody."""
        response = await client.get("/api/v1/readium/books/99999/positions.json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_book_without_an_epub_is_not_found(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        """Should answer 404 when the book was never given a file to read."""
        assert test_book.ebook_file is None

        response = await client.get(positions_url(test_book))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_unreadable_epub_is_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should fail the request rather than answer 404 for a book it cannot parse."""
        await store_epub(db_session, test_book, storage_dir, b"not an epub at all")

        response = await client.get(positions_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
