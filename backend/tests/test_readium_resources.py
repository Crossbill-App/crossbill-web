"""Tests for the endpoint serving a publication's own files to the web reader.

The paths asked for here are the manifest's hrefs with ``resources/`` stripped,
because that is exactly how a navigator reaches them: it resolves each href
against the manifest URL and fetches what comes out. So the fixtures are the
manifest's fixtures, and a name that survives the round trip through the URL is
the point rather than a detail -- ``nested_toc.epub`` carries a space and
non-ASCII letters, and ``LITERAL_PERCENT_EPUB`` carries a real percent sign,
which is the one name that a decode too many turns into a different file.

Only the files the manifest lists are reachable. The package document,
``META-INF/`` and the archive's ``mimetype`` member are in every EPUB and in no
publication, and the endpoint must not serve them.
"""

import zipfile
from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.main import app
from src.models import Book, User
from tests.conftest import create_test_book
from tests.test_readium_manifest import (
    LITERAL_PERCENT_EPUB,
    build_epub,
    fixture_bytes,
    store_epub,
)

CHAPTER_1 = "EPUB/text/chapter%201.xhtml"
CHAPTER_AANI = "EPUB/text/luku-%C3%A4%C3%A4ni.xhtml"
STYLESHEET = "EPUB/styles/main.css"
COVER_ART = "EPUB/images/cover%20art.png"


def resource_url(book: Book, href: str) -> str:
    """The URL a navigator resolves for a manifest href, ``resources/`` and all."""
    return f"/api/v1/readium/books/{book.id}/resources/{href}"


def member_bytes(epub_content: bytes, name: str) -> bytes:
    """What the archive really holds under ``name``, to compare a response against."""
    with zipfile.ZipFile(BytesIO(epub_content)) as archive:
        return archive.read(name)


@pytest.fixture
async def anonymous_client() -> AsyncGenerator[AsyncClient, None]:
    """A client with no authentication override, to see what the endpoint demands."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as unauthenticated:
        yield unauthenticated


@pytest.fixture
async def nested_toc_book(db_session: AsyncSession, test_book: Book, storage_dir: Path) -> Book:
    """A book whose EPUB has awkward file names, styles and an image."""
    await store_epub(db_session, test_book, storage_dir, fixture_bytes("nested_toc.epub"))
    return test_book


class TestServingPublicationFiles:
    """What GET /api/v1/readium/books/{id}/resources/{path} returns for a real book."""

    async def test_serves_a_chapter_unchanged(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should return the archive's own bytes under the declared media type."""
        response = await client.get(resource_url(nested_toc_book, CHAPTER_1))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.content == member_bytes(
            fixture_bytes("nested_toc.epub"), "EPUB/text/chapter 1.xhtml"
        )
        assert b"<html" in response.content
        assert response.headers["content-type"] == "application/xhtml+xml"
        assert response.headers["cache-control"] == "private"

    async def test_serves_a_stylesheet(self, client: AsyncClient, nested_toc_book: Book) -> None:
        """Should serve a supporting resource, not only the reading order."""
        response = await client.get(resource_url(nested_toc_book, STYLESHEET))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "text/css"
        assert response.content == member_bytes(
            fixture_bytes("nested_toc.epub"), "EPUB/styles/main.css"
        )

    async def test_serves_a_png_byte_for_byte(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should not re-encode binary content on its way out."""
        response = await client.get(resource_url(nested_toc_book, COVER_ART))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert response.content == member_bytes(
            fixture_bytes("nested_toc.epub"), "EPUB/images/cover art.png"
        )

    async def test_serves_a_name_with_non_ascii_letters(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should reach a UTF-8 file name through its percent-encoded href."""
        response = await client.get(resource_url(nested_toc_book, CHAPTER_AANI))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.content == member_bytes(
            fixture_bytes("nested_toc.epub"), "EPUB/text/luku-ääni.xhtml"
        )

    async def test_serves_a_file_whose_name_contains_a_percent_sign(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should decode the path exactly once, reaching the file that exists.

        The publication's one chapter is really named ``chapter%20one.xhtml``,
        so the manifest publishes ``chapter%2520one.xhtml``. Decoding that twice
        would name ``chapter one.xhtml``, which no EPUB here contains -- the
        request would 404 while the manifest kept advertising the href.
        """
        await store_epub(db_session, test_book, storage_dir, LITERAL_PERCENT_EPUB)

        response = await client.get(resource_url(test_book, "chapter%2520one.xhtml"))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "application/xhtml+xml"
        assert response.content == member_bytes(LITERAL_PERCENT_EPUB, "chapter%20one.xhtml")

    async def test_the_manifests_hrefs_all_resolve(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should serve every file the manifest names, with the type it named.

        A manifest that advertises an href this endpoint will not serve is the
        failure the two of them can only have together, so the manifest is what
        drives the requests rather than a list copied out of it.
        """
        manifest = (
            await client.get(f"/api/v1/readium/books/{nested_toc_book.id}/manifest.json")
        ).json()
        links = manifest["readingOrder"] + manifest["resources"]
        assert len(links) == 5

        for link in links:
            href = link["href"].removeprefix("resources/")
            response = await client.get(resource_url(nested_toc_book, href))

            assert response.status_code == status.HTTP_200_OK, link["href"]
            assert response.headers["content-type"] == link["type"], link["href"]
            assert response.content, link["href"]


class TestConditionalRequests:
    """The entity tag, and what a reader that already holds a file is told."""

    async def test_the_etag_is_stable_across_requests(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should tag the same bytes the same way, or no cache can ever hit."""
        first = await client.get(resource_url(nested_toc_book, CHAPTER_1))
        second = await client.get(resource_url(nested_toc_book, CHAPTER_1))

        assert first.headers["etag"] == second.headers["etag"]
        assert first.headers["etag"].startswith('"')

    async def test_different_files_get_different_etags(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should not tag two files of one book alike, or one would mask the other."""
        chapter = await client.get(resource_url(nested_toc_book, CHAPTER_1))
        stylesheet = await client.get(resource_url(nested_toc_book, STYLESHEET))

        assert chapter.headers["etag"] != stylesheet.headers["etag"]

    async def test_a_matching_if_none_match_is_answered_304(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should send the headers and no body when the caller's copy is current."""
        first = await client.get(resource_url(nested_toc_book, CHAPTER_1))
        etag = first.headers["etag"]

        response = await client.get(
            resource_url(nested_toc_book, CHAPTER_1), headers={"If-None-Match": etag}
        )

        assert response.status_code == status.HTTP_304_NOT_MODIFIED
        assert response.content == b""
        assert response.headers["etag"] == etag
        assert response.headers["cache-control"] == "private"

    async def test_a_weak_validator_still_matches(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should compare tags weakly, as RFC 9110 requires for a GET."""
        first = await client.get(resource_url(nested_toc_book, CHAPTER_1))

        response = await client.get(
            resource_url(nested_toc_book, CHAPTER_1),
            headers={"If-None-Match": f"W/{first.headers['etag']}"},
        )

        assert response.status_code == status.HTTP_304_NOT_MODIFIED

    async def test_a_stale_if_none_match_is_answered_with_the_file(
        self, client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should serve the file when the caller holds some other version."""
        response = await client.get(
            resource_url(nested_toc_book, CHAPTER_1),
            headers={"If-None-Match": '"not-the-one-we-serve"'},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content

    async def test_the_etag_changes_when_the_stored_file_changes(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should re-tag a file whose contents are unchanged but whose book's EPUB is not.

        A CRC alone would call these one resource: the chapter is byte-identical
        in both files. Replacing a book's EPUB has to invalidate what a reader
        cached for it, so the stored file's name is part of the tag.
        """
        await store_epub(
            db_session, test_book, storage_dir, fixture_bytes("nested_toc.epub"), "first.epub"
        )
        before = await client.get(resource_url(test_book, CHAPTER_1))

        await store_epub(
            db_session, test_book, storage_dir, fixture_bytes("nested_toc.epub"), "second.epub"
        )
        after = await client.get(resource_url(test_book, CHAPTER_1))

        assert before.status_code == after.status_code == status.HTTP_200_OK
        assert after.content == before.content
        assert after.headers["etag"] != before.headers["etag"]

    async def test_the_stale_etag_no_longer_matches(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should send the file rather than 304 to a reader holding the old book's tag."""
        await store_epub(
            db_session, test_book, storage_dir, fixture_bytes("nested_toc.epub"), "first.epub"
        )
        stale = (await client.get(resource_url(test_book, CHAPTER_1))).headers["etag"]

        await store_epub(
            db_session, test_book, storage_dir, fixture_bytes("nested_toc.epub"), "second.epub"
        )
        response = await client.get(
            resource_url(test_book, CHAPTER_1), headers={"If-None-Match": stale}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content


class TestOnlyPublicationFilesAreReachable:
    """What the endpoint refuses, which is everything the manifest does not name."""

    @pytest.mark.parametrize(
        ("path", "why"),
        [
            ("EPUB/package.opf", "the package document is not part of the publication"),
            ("META-INF/container.xml", "container metadata is not part of the publication"),
            ("mimetype", "the archive's own marker is not part of the publication"),
            ("EPUB/text/nowhere.xhtml", "no such member"),
            ("", "the resource root is not a file"),
        ],
    )
    async def test_a_path_the_manifest_does_not_list_is_not_found(
        self, client: AsyncClient, nested_toc_book: Book, path: str, why: str
    ) -> None:
        """Should serve only what the manifest advertises, whatever else the zip holds."""
        response = await client.get(resource_url(nested_toc_book, path))

        assert response.status_code == status.HTTP_404_NOT_FOUND, why

    @pytest.mark.parametrize(
        "path",
        [
            "..%2F..%2Fmanifest.json",
            "..%2F..%2F..%2F..%2Fetc%2Fpasswd",
            "%2Fetc%2Fpasswd",
            "/etc/passwd",
            "EPUB%2F..%2F..%2Fmanifest.json",
        ],
    )
    async def test_a_path_climbing_out_of_the_container_is_not_found(
        self, client: AsyncClient, nested_toc_book: Book, path: str
    ) -> None:
        """Should never resolve a path outside the publication, encoded or not.

        The membership check is the guard: the manifest's hrefs are already
        known not to escape the container, so nothing that escapes can be in the
        list, and there is no second normalisation step to get wrong.
        """
        response = await client.get(resource_url(nested_toc_book, path))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert b"root:" not in response.content

    async def test_a_media_type_that_is_not_one_is_not_echoed_back(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should not put a package document's text into a header unaltered.

        The media type is copied from a file the user uploaded. A value with a
        newline in it would smuggle a second header into the response, so
        anything that is not a plain ``type/subtype`` is replaced by one the
        browser will not act on.
        """
        await store_epub(
            db_session,
            test_book,
            storage_dir,
            build_epub(
                manifest_items=(
                    '<item id="c1" href="c1.xhtml" media-type="text/html&#10;Set-Cookie: pwned=1"/>'
                ),
                spine='<itemref idref="c1"/>',
                nav_links='<li><a href="c1.xhtml">One</a></li>',
                files=("c1.xhtml",),
            ),
        )

        response = await client.get(resource_url(test_book, "c1.xhtml"))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "application/octet-stream"
        assert "set-cookie" not in response.headers


class TestResourceAccess:
    """Who may read a publication's files, and what happens when there are none."""

    async def test_requires_authentication(
        self, anonymous_client: AsyncClient, nested_toc_book: Book
    ) -> None:
        """Should reject an unauthenticated request rather than serve the file."""
        response = await anonymous_client.get(resource_url(nested_toc_book, CHAPTER_1))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_another_users_book_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        storage_dir: Path,
    ) -> None:
        """Should answer 404 for a readable file belonging to somebody else."""
        their_book = await create_test_book(
            db_session=db_session, user_id=other_user.id, title="Not Yours"
        )
        await store_epub(db_session, their_book, storage_dir, fixture_bytes("nested_toc.epub"))

        response = await client.get(resource_url(their_book, CHAPTER_1))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert b"<html" not in response.content

    async def test_unknown_book_is_not_found(self, client: AsyncClient) -> None:
        """Should answer 404 for a book id that exists for nobody."""
        response = await client.get(
            f"/api/v1/readium/books/99999/resources/{CHAPTER_1}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_book_without_an_epub_is_not_found(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        """Should answer 404 when the book was never given a file to read."""
        assert test_book.ebook_file is None

        response = await client.get(resource_url(test_book, CHAPTER_1))

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

        response = await client.get(resource_url(test_book, CHAPTER_1))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
