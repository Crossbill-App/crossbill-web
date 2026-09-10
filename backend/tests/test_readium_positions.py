"""Tests for the position list a publication's manifest links to.

A *position* is Readium's synthetic page: a reflowable EPUB has no pages of its
own, so the reading order is cut into 1024-byte pieces and each piece gets a
Locator. The numbers are a convention, and a convention is only worth anything
if everyone computes it identically -- so the assertions here are exact values
rather than shapes, because "some monotone sequence" would pass for a numbering
no other Readium implementation would reproduce.

The cut is made on the uncompressed sizes the stored index already holds, so
most tests here write an index whose sizes are chosen rather than an EPUB whose
sizes are incidental: ``minimal.epub``'s chapters are a few hundred bytes each
and would be one position however the arithmetic went. ``nested_toc.epub`` still
stands behind the one thing a hand-written index cannot show -- that a position's
href is the percent-encoded string the manifest gave the reader.
"""

from urllib.parse import urljoin

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationLayout,
    PublicationMetadata,
    PublicationResource,
)
from src.application.web_reader.queries.publication_positions import (
    MAX_PUBLICATION_POSITIONS,
    POSITION_LENGTH,
)
from tests.readium_helpers import (
    POSITION_LIST_MEDIA_TYPE,
    POSITION_LIST_REL,
    another_users_book,
    manifest_url,
    positions_url,
    store_fixture,
    store_publication,
)

XHTML = "application/xhtml+xml"


def chapter(href: str, size: int, layout: PublicationLayout | None = None) -> PublicationResource:
    return PublicationResource(href=href, media_type=XHTML, size=size, layout=layout)


def publication_of(*reading_order: PublicationResource) -> ParsedPublication:
    """A publication that is nothing but a reading order of chosen sizes."""
    return ParsedPublication(
        metadata=PublicationMetadata(
            title="Sized To Order", author=None, language="en", identifier=None
        ),
        reading_order=reading_order,
        resources=(),
        toc=(),
        content_hash="0" * 64,
    )


@pytest.fixture
async def long_chapters_book(db_session: AsyncSession, test_book: models.Book) -> models.Book:
    """A book whose two chapters straddle the 1024-byte cut, two positions each.

    The second is one byte over a single position, so a count that truncated
    instead of rounding up would lose the last byte of the book.
    """
    await store_publication(
        db_session,
        test_book,
        publication_of(chapter("c1.xhtml", 2048), chapter("c2.xhtml", 1025)),
    )
    return test_book


class TestThePositionList:
    """What GET /api/v1/readium/books/{id}/positions.json contains."""

    async def test_cuts_each_chapter_into_a_position_per_kilobyte(
        self, client: AsyncClient, long_chapters_book: models.Book
    ) -> None:
        """Should number a 2048-byte and a 1025-byte chapter as two positions each."""
        response = await client.get(positions_url(long_chapters_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"].startswith(POSITION_LIST_MEDIA_TYPE)
        assert response.json() == {
            "total": 4,
            "positions": [
                {
                    "href": "resources/c1.xhtml",
                    "type": XHTML,
                    "locations": {"position": 1, "progression": 0.0, "totalProgression": 0.0},
                },
                {
                    "href": "resources/c1.xhtml",
                    "type": XHTML,
                    "locations": {"position": 2, "progression": 0.5, "totalProgression": 0.25},
                },
                {
                    "href": "resources/c2.xhtml",
                    "type": XHTML,
                    "locations": {"position": 3, "progression": 0.0, "totalProgression": 0.5},
                },
                {
                    "href": "resources/c2.xhtml",
                    "type": XHTML,
                    "locations": {"position": 4, "progression": 0.5, "totalProgression": 0.75},
                },
            ],
        }

    async def test_a_fixed_layout_page_is_one_position_however_long(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should give a pre-paginated page one position and its reflowable neighbour four.

        Both documents run to 4096 bytes, so layout is the only thing that can
        make one of them a single position.
        """
        await store_publication(
            db_session,
            test_book,
            publication_of(
                chapter("p1.xhtml", 4096, PublicationLayout.FIXED),
                chapter("p2.xhtml", 4096, PublicationLayout.REFLOWABLE),
            ),
        )

        response = await client.get(positions_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        document = response.json()
        assert document["total"] == 5
        assert [position["href"] for position in document["positions"]] == [
            "resources/p1.xhtml",
            "resources/p2.xhtml",
            "resources/p2.xhtml",
            "resources/p2.xhtml",
            "resources/p2.xhtml",
        ]
        assert [position["locations"] for position in document["positions"]] == [
            {"position": 1, "progression": 0.0, "totalProgression": 0.0},
            {"position": 2, "progression": 0.0, "totalProgression": 0.2},
            {"position": 3, "progression": 0.25, "totalProgression": 0.4},
            {"position": 4, "progression": 0.5, "totalProgression": 0.6},
            {"position": 5, "progression": 0.75, "totalProgression": 0.8},
        ]

    async def test_only_the_reading_order_gets_positions(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should number neither a stylesheet, an image nor the navigation document.

        None is a place a reader can be, and counting them would push every real
        position's number off by the size of the book's assets.
        """
        await store_fixture(db_session, test_book, "nested_toc")

        document = (await client.get(positions_url(test_book.id))).json()

        assert document["total"] == 2
        assert [position["href"] for position in document["positions"]] == [
            "resources/EPUB/text/chapter%201.xhtml",
            "resources/EPUB/text/luku-%C3%A4%C3%A4ni.xhtml",
        ]

    async def test_refuses_a_publication_declaring_too_many_positions(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should refuse to cut up a chapter that only claims to be enormous."""
        await store_publication(
            db_session,
            test_book,
            publication_of(
                chapter("huge.xhtml", (MAX_PUBLICATION_POSITIONS + 1) * POSITION_LENGTH)
            ),
        )

        response = await client.get(positions_url(test_book.id))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.content) < 1024


class TestPositionListAccess:
    """Who the position list is served to."""

    async def test_another_users_book_is_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Should refuse a book the caller does not own, stored index and all."""
        their_book = await another_users_book(db_session)
        await store_fixture(db_session, their_book, "minimal")

        response = await client.get(positions_url(their_book.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_unknown_book_is_not_found(self, client: AsyncClient) -> None:
        """Should answer 404 for a book id that names nothing."""
        response = await client.get(positions_url(999999))

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestThePositionListIsReachedFromTheManifest:
    """The link is the contract: a reader only ever gets here by following it."""

    async def test_the_manifests_position_list_link_resolves(
        self, client: AsyncClient, long_chapters_book: models.Book
    ) -> None:
        """Should serve the position list at the href the manifest advertises.

        The href is relative, so what is followed here is a navigator's own
        resolution of it rather than a path copied out of the router.
        """
        manifest_response = await client.get(manifest_url(long_chapters_book.id))
        link = next(
            link for link in manifest_response.json()["links"] if link["rel"] == POSITION_LIST_REL
        )

        resolved = urljoin(str(manifest_response.url), link["href"])
        response = await client.get(resolved)

        assert response.status_code == status.HTTP_200_OK, resolved
        assert response.headers["content-type"].startswith(link["type"])
        assert response.json()["total"] == 4
