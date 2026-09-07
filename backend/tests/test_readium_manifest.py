"""Tests for the Readium Web Publication Manifest endpoint.

Three fixture EPUBs stand behind these, each carrying what the others do not:

- ``minimal.epub`` (from M0.3): the plain case -- two spine chapters, a
  navigation document that is not in the spine, no author, no styling.
- ``nested_toc.epub``: a package document one directory down, a two-level
  navigation document, styles and an image among the resources, and file names
  with a space and with non-ASCII letters, which is what makes percent-encoding
  observable rather than incidental.
- ``fixed_layout.epub``: ``rendition:layout`` stated for the publication and
  overridden on one spine item, the only source of Readium's
  ``properties.layout``.

The hrefs asserted here are the same strings ``xpoint-cfi`` puts in a derived
Locator's ``href`` -- relative to the EPUB container root, percent-encoded --
prefixed with the path the resource endpoint will serve them from (M1.2). A
highlight cannot be anchored to a resource the manifest names differently, so
that agreement is the point rather than a formatting preference.
"""

import zipfile
from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.main import app
from src.models import Book, User
from tests.conftest import create_test_book

FIXTURES = Path(__file__).parent / "fixtures"

WEBPUB_MEDIA_TYPE = "application/webpub+json"
EPUB_PROFILE = "https://readium.org/webpub-manifest/profiles/epub"
POSITION_LIST_REL = "http://readium.org/position-list"


def manifest_url(book: Book) -> str:
    return f"/api/v1/readium/books/{book.id}/manifest.json"


async def store_epub(
    db_session: AsyncSession,
    book: Book,
    storage_dir: Path,
    content: bytes,
    filename: str = "book.epub",
) -> None:
    """Attach an EPUB to a book, both on disk and on the row that names it."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / filename).write_bytes(content)
    book.ebook_file = filename
    book.file_type = "epub"
    await db_session.commit()


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def without_title(epub_content: bytes) -> bytes:
    """Rebuild an EPUB with its ``dc:title`` removed -- invalid, but it happens."""
    source = zipfile.ZipFile(BytesIO(epub_content))
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as rebuilt:
        for entry in source.namelist():
            body = source.read(entry)
            if entry.endswith(".opf"):
                text = body.decode()
                start = text.index("<dc:title>")
                end = text.index("</dc:title>") + len("</dc:title>")
                body = (text[:start] + text[end:]).encode()
            rebuilt.writestr(entry, body)
    return out.getvalue()


@pytest.fixture
async def anonymous_client() -> AsyncGenerator[AsyncClient, None]:
    """A client with no authentication override, to see what the endpoint demands."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as unauthenticated:
        yield unauthenticated


class TestManifestStructure:
    """The manifest a reader receives for GET /api/v1/readium/books/{id}/manifest.json."""

    async def test_renders_the_whole_publication(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should serve metadata, reading order, resources, TOC and links as webpub JSON."""
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(manifest_url(test_book))

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
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should carry an absolute self link and a relative position-list link."""
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(manifest_url(test_book))

        assert response.json()["links"] == [
            {
                "href": f"http://test{manifest_url(test_book)}",
                "rel": "self",
                "type": WEBPUB_MEDIA_TYPE,
            },
            {"href": "positions.json", "rel": POSITION_LIST_REL, "type": "application/json"},
        ]

    async def test_nests_the_toc_and_percent_encodes_hrefs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should keep TOC nesting, and encode spaced and non-ASCII names once."""
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("nested_toc.epub"))

        response = await client.get(manifest_url(test_book))

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
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should apply the publication's rendition:layout, and any spine override."""
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("fixed_layout.epub"))

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        manifest = response.json()
        assert [item["properties"] for item in manifest["readingOrder"]] == [
            {"layout": "fixed"},
            {"layout": "reflowable"},
        ]
        # The navigation document is not read through, so it states no layout.
        assert "properties" not in manifest["resources"][0]

    async def test_omits_layout_when_the_publication_states_none(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should leave layout out rather than guess a default for the reader."""
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(manifest_url(test_book))

        assert all("properties" not in item for item in response.json()["readingOrder"])

    async def test_falls_back_to_the_library_title(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should title the manifest from the book row when the EPUB names no title."""
        await store_epub(
            db_session, test_book, storage_dir, without_title(fixture_bytes("minimal.epub"))
        )

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["metadata"]["title"] == test_book.title == "Test Book"


class TestManifestAccess:
    """Who may read a manifest, and what happens when there is none to read."""

    async def test_requires_authentication(
        self, anonymous_client: AsyncClient, test_book: Book
    ) -> None:
        """Should reject an unauthenticated request rather than serve the book."""
        response = await anonymous_client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_unknown_book_is_not_found(self, client: AsyncClient) -> None:
        """Should answer 404 for a book id that exists for nobody."""
        response = await client.get("/api/v1/readium/books/99999/manifest.json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_another_users_book_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        storage_dir: Path,
    ) -> None:
        """Should answer 404 for a readable EPUB belonging to somebody else."""
        stranger = User(email="stranger@example.com", hashed_password="x")
        db_session.add(stranger)
        await db_session.commit()
        await db_session.refresh(stranger)
        assert stranger.id != test_user.id

        their_book = await create_test_book(
            db_session=db_session, user_id=stranger.id, title="Not Yours"
        )
        await store_epub(db_session, their_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(manifest_url(their_book))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_book_without_an_epub_is_not_found(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        """Should answer 404 when the book was never given a file to read."""
        assert test_book.ebook_file is None

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_missing_epub_file_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should answer 404 when the row names a file the store does not hold."""
        test_book.ebook_file = "vanished.epub"
        test_book.file_type = "epub"
        await db_session.commit()

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_unreadable_epub_is_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should fail the request rather than serve a manifest with nothing in it."""
        await store_epub(db_session, test_book, storage_dir, b"not an epub at all")

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_fixture_hrefs_match_derived_locators() -> None:
    """The manifest's hrefs must be the ones a highlight's Locator will name.

    Asserted against ``xpoint-cfi`` directly, because a disagreement here would
    surface much later as a highlight that renders nowhere (ADR-0004 §2), and
    the endpoint tests above cannot see it: both sides would simply be wrong in
    the same file.
    """
    import xpoint_cfi  # noqa: PLC0415

    publication: Any = xpoint_cfi.EpubMap.from_bytes(fixture_bytes("nested_toc.epub"))
    locator = xpoint_cfi.xpoint_to_locator(
        publication, "/body/DocFragment[1]/body/div/p[1]/text().0"
    )

    assert locator.href == "EPUB/text/chapter%201.xhtml"
