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

import zipfile
from pathlib import Path
from urllib.parse import urljoin

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.web_reader.queries import publication_positions_query
from src.infrastructure.web_reader.queries.publication_resource_query import MAX_RESOURCE_BYTES
from src.models import Book
from tests.test_readium_manifest import (
    POSITION_LIST_MEDIA_TYPE,
    POSITION_LIST_REL,
    build_epub,
    fixture_bytes,
    manifest_url,
    store_epub,
    with_declared_size,
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


# A publication whose one spine document is a few hundred bytes and says it is
# nearly two gigabytes. Nothing here is decompressed, so the declaration is the
# only thing the position count can be built on -- and the archive is 1.3 KB, so
# the cost of answering it has nothing to do with the cost of sending it.
def overstating_epub(declared: int) -> bytes:
    """An EPUB whose one spine document claims to hold ``declared`` bytes."""
    return with_declared_size(
        build_epub(
            manifest_items=('<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'),
            spine='<itemref idref="c1"/>',
            nav_links='<li><a href="c1.xhtml">One</a></li>',
            files=("c1.xhtml",),
            compression=zipfile.ZIP_DEFLATED,
        ),
        declared=declared,
    )


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


class TestAHostileDeclarationIsBounded:
    """What a publication may claim about itself, and what claiming it costs.

    Positions are counted from sizes the archive *declares*, because counting
    them from the real ones would mean decompressing the whole book. A
    declaration is free to write, so this endpoint is the one place where a
    small file can ask for an enormous answer: every position becomes an object,
    a model and a JSON object on the way out.
    """

    async def test_refuses_a_spine_member_declaring_more_than_the_resource_cap(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should refuse a member the resource endpoint would refuse to serve.

        Deliberately one byte over the per-member cap and no further, so the
        publication-wide ceiling cannot be what refuses it: 64 MiB is 65,536
        positions, comfortably inside a publication's allowance. Only the
        member's own size can turn this away, which is the point -- a reader
        that cannot fetch the member has no use for its positions, so the two
        endpoints answer alike.
        """
        oversized = overstating_epub(MAX_RESOURCE_BYTES + 1)
        assert len(oversized) < 2048, "the archive is tiny; only its declaration is not"
        await store_epub(db_session, test_book, storage_dir, oversized)

        response = await client.get(positions_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.content) < 1024

    async def test_refuses_a_member_declaring_more_than_the_publication_may_hold(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should refuse the two-gigabyte claim that started this, and cheaply.

        A 1.3 KB archive declaring a two-gigabyte chapter asks to be cut into
        two million positions. Before the bounds it was answered: 200 OK after
        thirteen seconds, carrying a response the size of the book it was only
        pretending to be.
        """
        await store_epub(db_session, test_book, storage_dir, overstating_epub(2**31 - 65536))

        response = await client.get(positions_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.content) < 1024

    async def test_refuses_a_publication_declaring_too_many_positions(
        self,
        client: AsyncClient,
        long_chapters_book: Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should bound the whole list, not only each member of it.

        The per-member cap leaves a publication free to spend it many times
        over: enough members just under the cap still add up to millions of
        positions. The ceiling is lowered rather than the fixture inflated,
        because a fixture big enough to trip the real one would only be slow.
        """
        monkeypatch.setattr(publication_positions_query, "MAX_PUBLICATION_POSITIONS", 3)

        response = await client.get(positions_url(long_chapters_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_an_honest_book_is_unaffected_by_either_bound(
        self, client: AsyncClient, long_chapters_book: Book
    ) -> None:
        """Should still serve a book whose members are what they say they are.

        The bounds are worth nothing if they also turn away real publications,
        and the fixture's four positions sit far under both.
        """
        response = await client.get(positions_url(long_chapters_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["total"] == 4


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
