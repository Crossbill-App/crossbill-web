"""Tests for the Readium Web Publication Manifest endpoint.

The endpoint renders the index stored beside a book at upload, so every test
here writes a row rather than an EPUB: the archives on disk are only a
convenient way to produce a realistic one.

Three fixture EPUBs stand behind these, each carrying what the others do not:

- ``minimal.epub``: the plain case -- two spine chapters, a navigation document
  that is not in the spine, no author, no styling.
- ``nested_toc.epub``: a package document one directory down, a two-level
  navigation document, styles and an image among the resources, and file names
  with a space and with non-ASCII letters, which is what makes percent-encoding
  observable rather than incidental.
- ``fixed_layout.epub``: ``rendition:layout`` stated for the publication and
  overridden on one spine item, the only source of Readium's
  ``properties.layout``.

The hrefs asserted here are the same strings ``xpoint-cfi`` puts in a derived
Locator's ``href`` -- relative to the EPUB container root, percent-encoded --
prefixed with the path the resource endpoint will serve them from. A highlight
cannot be anchored to a resource the manifest names differently, so that
agreement is the point rather than a formatting preference.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationMetadata,
    PublicationResource,
    TocEntry,
)
from src.config import get_settings
from src.domain.common.value_objects import BookId
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.repositories.publication_repository import PublicationRepository
from src.infrastructure.web_reader.schemas.locator_builders import RESOURCE_PATH_PREFIX
from tests.conftest import create_test_book

FIXTURES = Path(__file__).parent / "fixtures"

WEBPUB_MEDIA_TYPE = "application/webpub+json"
EPUB_PROFILE = "https://readium.org/webpub-manifest/profiles/epub"
POSITION_LIST_REL = "http://readium.org/position-list"
POSITION_LIST_MEDIA_TYPE = "application/vnd.readium.position-list+json"


def manifest_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/manifest.json"


def parse_fixture(name: str) -> ParsedPublication:
    return read_publication((FIXTURES / f"{name}.epub").read_bytes())


async def store_publication(
    db_session: AsyncSession,
    book: models.Book,
    publication: ParsedPublication,
    file_name: str = "book.epub",
) -> None:
    """Store a book's publication index, the way the upload does."""
    await PublicationRepository(db_session).save(BookId(book.id), file_name, publication)


async def store_fixture(db_session: AsyncSession, book: models.Book, name: str) -> None:
    await store_publication(db_session, book, parse_fixture(name), f"{name}.epub")


class TestManifestStructure:
    """The manifest a reader receives for GET /api/v1/readium/books/{id}/manifest.json."""

    async def test_renders_the_whole_publication(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should serve metadata, reading order, resources, TOC and links as webpub JSON."""
        await store_fixture(db_session, test_book, "minimal")

        response = await client.get(manifest_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"].startswith(WEBPUB_MEDIA_TYPE)

        manifest = response.json()
        assert manifest["@context"] == "https://readium.org/webpub-manifest/context.jsonld"
        assert manifest["metadata"] == {
            "@type": "http://schema.org/Book",
            "conformsTo": EPUB_PROFILE,
            "identifier": "urn:uuid:8f1a0c2e-0000-4000-8000-000000000001",
            "title": "The Lantern Fixture",
            "language": "en",
        }
        assert manifest["readingOrder"] == [
            {"href": "resources/OEBPS/chapter1.xhtml", "type": "application/xhtml+xml"},
            {"href": "resources/OEBPS/chapter2.xhtml", "type": "application/xhtml+xml"},
        ]
        assert manifest["resources"] == [
            {"href": "resources/OEBPS/nav.xhtml", "type": "application/xhtml+xml"},
        ]
        assert manifest["toc"] == [
            {"href": "resources/OEBPS/chapter1.xhtml", "title": "Chapter One"},
            {"href": "resources/OEBPS/chapter2.xhtml", "title": "Chapter Two"},
        ]

    async def test_links_to_itself_and_to_the_position_list(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should link to the request URL when no public origin is configured."""
        assert get_settings().PUBLIC_BASE_URL == ""
        await store_fixture(db_session, test_book, "minimal")

        response = await client.get(manifest_url(test_book.id))

        assert response.json()["links"] == [
            {
                "href": f"http://test{manifest_url(test_book.id)}",
                "rel": "self",
                "type": WEBPUB_MEDIA_TYPE,
            },
            {
                "href": "positions.json",
                "rel": POSITION_LIST_REL,
                "type": POSITION_LIST_MEDIA_TYPE,
            },
        ]

    async def test_self_link_uses_the_configured_public_origin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should build the self link from PUBLIC_BASE_URL, not from the request's own origin."""
        monkeypatch.setattr(get_settings(), "PUBLIC_BASE_URL", "https://reader.example.com")
        await store_fixture(db_session, test_book, "minimal")

        response = await client.get(manifest_url(test_book.id))

        self_link = response.json()["links"][0]
        assert self_link["href"] == f"https://reader.example.com{manifest_url(test_book.id)}"

    async def test_nests_the_toc_and_percent_encodes_hrefs(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should keep TOC nesting, and encode spaced and non-ASCII names once."""
        await store_fixture(db_session, test_book, "nested_toc")

        response = await client.get(manifest_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        manifest = response.json()
        assert manifest["metadata"]["title"] == "Kirjan Ääni"
        assert manifest["metadata"]["author"] == "Émile Zola"
        assert manifest["metadata"]["language"] == "fi"
        assert manifest["readingOrder"] == [
            {
                "href": "resources/EPUB/text/chapter%201.xhtml",
                "type": "application/xhtml+xml",
            },
            {
                "href": "resources/EPUB/text/luku-%C3%A4%C3%A4ni.xhtml",
                "type": "application/xhtml+xml",
            },
        ]
        assert manifest["resources"] == [
            {"href": "resources/EPUB/nav.xhtml", "type": "application/xhtml+xml"},
            {"href": "resources/EPUB/styles/main.css", "type": "text/css"},
            {"href": "resources/EPUB/images/cover%20art.png", "type": "image/png"},
        ]
        assert manifest["toc"] == [
            {
                "href": "resources/EPUB/text/chapter%201.xhtml",
                "title": "Part One",
                "children": [
                    {
                        "href": "resources/EPUB/text/chapter%201.xhtml#sec1",
                        "title": "Chapter One",
                    },
                    {
                        "href": "resources/EPUB/text/luku-%C3%A4%C3%A4ni.xhtml",
                        "title": "Luku Ääni",
                    },
                ],
            },
            {
                "href": "resources/EPUB/text/luku-%C3%A4%C3%A4ni.xhtml#loppu",
                "title": "Appendix",
            },
        ]

    async def test_reports_the_layout_of_each_reading_order_item(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should apply the publication's rendition:layout, and any spine override."""
        await store_fixture(db_session, test_book, "fixed_layout")

        response = await client.get(manifest_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        manifest = response.json()
        assert [item["properties"] for item in manifest["readingOrder"]] == [
            {"layout": "fixed"},
            {"layout": "reflowable"},
        ]
        # The navigation document is not read through, so it states no layout.
        assert "properties" not in manifest["resources"][0]

    async def test_renders_a_toc_heading_that_links_nowhere(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should keep an unlinked heading's title and children, pointing it at '#'."""
        await store_publication(
            db_session,
            test_book,
            ParsedPublication(
                metadata=PublicationMetadata(
                    title="Headings", author=None, language="en", identifier=None
                ),
                reading_order=(
                    PublicationResource(
                        href="c1.xhtml", media_type="application/xhtml+xml", size=100
                    ),
                ),
                resources=(),
                toc=(
                    TocEntry(
                        title="Part One",
                        href=None,
                        children=(TocEntry(title="Chapter One", href="c1.xhtml"),),
                    ),
                ),
                content_hash="0" * 64,
            ),
        )

        response = await client.get(manifest_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["toc"] == [
            {
                "href": "#",
                "title": "Part One",
                "children": [{"href": "resources/c1.xhtml", "title": "Chapter One"}],
            }
        ]

    async def test_falls_back_to_the_library_title(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Should title the manifest from the book row when the EPUB names no title."""
        publication = parse_fixture("minimal")
        await store_publication(
            db_session,
            test_book,
            replace(publication, metadata=replace(publication.metadata, title=None)),
        )

        response = await client.get(manifest_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["metadata"]["title"] == test_book.title == "Test Book"


class TestManifestAccess:
    """Who the manifest is served to."""

    async def test_another_users_book_is_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Should refuse a book the caller does not own, stored index and all."""
        intruder = models.User(email="intruder@test.com")
        db_session.add(intruder)
        await db_session.commit()
        await db_session.refresh(intruder)
        their_book = await create_test_book(
            db_session, user_id=intruder.id, title="Not Yours", author="Someone"
        )
        await store_fixture(db_session, their_book, "minimal")

        response = await client.get(manifest_url(their_book.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_unknown_book_is_not_found(self, client: AsyncClient) -> None:
        """Should answer 404 for a book id that names nothing."""
        response = await client.get(manifest_url(999999))

        assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_manifest_hrefs_match_derived_locators(
    client: AsyncClient, db_session: AsyncSession, test_book: models.Book
) -> None:
    """The manifest's hrefs must be the ones a highlight's Locator will name.

    Asserted against ``xpoint-cfi`` rather than a second hardcoded string,
    because a disagreement here would surface much later as a highlight that
    renders nowhere (ADR-0004 §2), and a test pinning both sides to the same
    literal cannot see it: both would simply be wrong in the same file.
    """
    import xpoint_cfi  # noqa: PLC0415

    await store_fixture(db_session, test_book, "nested_toc")
    publication: Any = xpoint_cfi.EpubMap.from_bytes((FIXTURES / "nested_toc.epub").read_bytes())
    locator = xpoint_cfi.xpoint_to_locator(
        publication, "/body/DocFragment[1]/body/div/p[1]/text().0"
    )

    response = await client.get(manifest_url(test_book.id))

    served = response.json()["readingOrder"][0]["href"]
    assert served.removeprefix(RESOURCE_PATH_PREFIX) == locator.href
    assert served != locator.href, "the manifest href must carry the resource prefix"
