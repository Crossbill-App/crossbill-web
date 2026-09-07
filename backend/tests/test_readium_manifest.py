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

import struct
import zipfile
from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.library.services import epub_parser_service
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


def build_epub(
    manifest_items: str,
    spine: str,
    nav_links: str,
    files: tuple[str, ...] = (),
) -> bytes:
    """Assemble an EPUB by hand, so an adversarial one reads as such in the diff.

    The fixture files on disk are ordinary books; these are the shapes a hostile
    or broken publication takes, and writing the OPF out here is what makes the
    attack visible next to the assertion about it.
    """
    package = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="i">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:identifier id="i">urn:uuid:hand-built</dc:identifier>'
        "<dc:title>Hand Built</dc:title><dc:language>en</dc:language></metadata>\n"
        '  <manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
        f'properties="nav"/>{manifest_items}</manifest>\n'
        f"  <spine>{spine}</spine>\n</package>\n"
    )
    nav = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
        "<head><title>Contents</title></head>"
        f'<body><nav epub:type="toc"><ol>{nav_links}</ol></nav></body></html>'
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page</title></head>'
        "<body><div><p>Hi there.</p></div></body></html>"
    )

    out = BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        archive.writestr("content.opf", package)
        archive.writestr("nav.xhtml", nav)
        for name in files:
            archive.writestr(name, document)
    return out.getvalue()


# A publication whose one spine document is really named `chapter%20one.xhtml`
# -- a literal percent sign in the file name, which the OPF therefore writes as
# `chapter%2520one.xhtml`.
LITERAL_PERCENT_EPUB = build_epub(
    manifest_items=(
        '<item id="c1" href="chapter%2520one.xhtml" media-type="application/xhtml+xml"/>'
    ),
    spine='<itemref idref="c1"/>',
    nav_links='<li><a href="chapter%2520one.xhtml">Chapter One</a></li>',
    files=("chapter%20one.xhtml",),
)


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


class TestMalformedPublications:
    """What the endpoint does with an EPUB that is hostile, broken, or merely odd."""

    async def test_encodes_a_literal_percent_in_a_filename_once(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should name the file that exists, not the one its encoding decodes to.

        ebooklib decodes manifest hrefs and leaves navigation hrefs as written,
        so decoding both would turn the real file ``chapter%20one.xhtml`` into
        ``chapter one.xhtml`` in the reading order while the TOC still named the
        real one -- two hrefs for one file, neither reachable in both places.
        """
        await store_epub(db_session, test_book, storage_dir, LITERAL_PERCENT_EPUB)

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        manifest = response.json()
        expected = "resources/chapter%2520one.xhtml"
        assert manifest["readingOrder"][0]["href"] == expected
        assert manifest["toc"][0]["href"] == expected

    def test_literal_percent_href_matches_the_derived_locator(self) -> None:
        """The awkward name must agree with xpoint-cfi too, not just with itself."""
        import xpoint_cfi  # noqa: PLC0415

        publication: Any = xpoint_cfi.EpubMap.from_bytes(LITERAL_PERCENT_EPUB)
        locator = xpoint_cfi.xpoint_to_locator(
            publication, "/body/DocFragment[1]/body/div/p[1]/text().0"
        )

        assert locator.href == "chapter%2520one.xhtml"

    async def test_drops_toc_hrefs_that_escape_the_container(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should not let a TOC link resolve to another endpoint under the book's URL.

        ``resources/../../positions.json`` resolves against the manifest URL to
        a sibling endpoint, so the entry keeps its title and loses its href.
        """
        await store_epub(
            db_session,
            test_book,
            storage_dir,
            build_epub(
                manifest_items=(
                    '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                ),
                spine='<itemref idref="c1"/>',
                nav_links=(
                    '<li><a href="../../positions.json">Escape</a></li>'
                    '<li><a href="/etc/passwd">Absolute</a></li>'
                    '<li><a href="..%2F..%2Fpositions.json">Encoded escape</a></li>'
                    '<li><a href="c1.xhtml">Honest</a></li>'
                ),
                files=("c1.xhtml",),
            ),
        )

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["toc"] == [
            {"href": "#", "title": "Escape"},
            {"href": "#", "title": "Absolute"},
            {"href": "#", "title": "Encoded escape"},
            {"href": "resources/c1.xhtml", "title": "Honest"},
        ]

    async def test_rejects_a_publication_with_an_empty_spine(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should fail rather than serve a manifest with nothing to read."""
        await store_epub(
            db_session,
            test_book,
            storage_dir,
            build_epub(
                manifest_items=(
                    '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                ),
                spine="",
                nav_links='<li><a href="c1.xhtml">One</a></li>',
                files=("c1.xhtml",),
            ),
        )

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_rejects_a_publication_whose_spine_names_nothing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should fail when every idref dangles, rather than drop them silently."""
        await store_epub(
            db_session,
            test_book,
            storage_dir,
            build_epub(
                manifest_items=(
                    '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                ),
                spine='<itemref idref="nowhere"/>',
                nav_links='<li><a href="c1.xhtml">One</a></li>',
                files=("c1.xhtml",),
            ),
        )

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_rejects_an_archive_declaring_too_many_entries(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should turn a book away on its own central directory, before reading it.

        The limit is lowered rather than the fixture inflated: the guard reads
        the declared shape, so a real 10,000-entry archive would only make the
        test slow, not more truthful.
        """
        monkeypatch.setattr(epub_parser_service, "MAX_PUBLICATION_ENTRIES", 3)
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_rejects_too_many_entries_before_opening_the_archive(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should turn the book away on its declared count, not after parsing it.

        ``ZipFile`` builds a ``ZipInfo`` per entry inside its constructor, so a
        limit that only reads ``infolist()`` has already paid the allocation it
        exists to prevent -- 200,000 empty members fit in a 17 MB archive and
        cost about 100 MB to open. Only the ordering separates the two checks
        from outside, so the spy is the assertion.
        """
        opened: list[object] = []
        real_zipfile = zipfile.ZipFile

        def spy(*args: Any, **kwargs: Any) -> zipfile.ZipFile:  # noqa: ANN401
            opened.append(args[0] if args else None)
            return real_zipfile(*args, **kwargs)

        monkeypatch.setattr(epub_parser_service, "MAX_PUBLICATION_ENTRIES", 3)
        monkeypatch.setattr(epub_parser_service.zipfile, "ZipFile", spy)
        # minimal.epub holds six members, over the lowered cap.
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert opened == [], "the archive was opened despite declaring too many entries"

    async def test_rejects_an_archive_whose_declared_count_lies_low(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should still catch an over-cap archive that understates its own count.

        Reading the trailer means trusting it, so the check against the members
        ``ZipFile`` actually found has to stay. An EOCD that lies low gets past
        the cheap guard and is caught by the real one.
        """
        understated = bytearray(fixture_bytes("minimal.epub"))
        eocd = understated.rfind(b"PK\x05\x06")
        struct.pack_into("<H", understated, eocd + 10, 1)

        monkeypatch.setattr(epub_parser_service, "MAX_PUBLICATION_ENTRIES", 3)
        await store_epub(db_session, test_book, storage_dir, bytes(understated))

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_rejects_an_archive_declaring_too_much_content(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should turn away an archive whose declared uncompressed size is absurd."""
        monkeypatch.setattr(epub_parser_service, "MAX_PUBLICATION_UNCOMPRESSED_BYTES", 10)
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(manifest_url(test_book))

        assert response.status_code == status.HTTP_400_BAD_REQUEST


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
