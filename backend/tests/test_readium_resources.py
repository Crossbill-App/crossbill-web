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
from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.repositories.publication_repository import PublicationRepository
from src.main import settings as main_settings
from tests.readium_helpers import (
    LITERAL_PERCENT_EPUB,
    another_users_book,
    build_epub,
    fixture_bytes,
    manifest_url,
    store_publication,
)
from tests.test_readium_manifest import store_epub

CHAPTER_1 = "EPUB/text/chapter%201.xhtml"
CHAPTER_AANI = "EPUB/text/luku-%C3%A4%C3%A4ni.xhtml"
STYLESHEET = "EPUB/styles/main.css"
COVER_ART = "EPUB/images/cover%20art.png"


def resource_url(book_id: int, href: str) -> str:
    """The URL a navigator resolves for a manifest href, ``resources/`` and all."""
    return f"/api/v1/readium/books/{book_id}/resources/{href}"


async def store_indexed_epub(
    db_session: AsyncSession,
    book: models.Book,
    storage_dir: Path,
    content: bytes,
    filename: str = "book.epub",
) -> None:
    """Give a book an EPUB on disk and the index row that names it.

    The endpoint reads the file name off the index row, so a book with only one
    of the two is a book in mid-upload rather than one ready to be read.
    """
    await store_epub(db_session, book, storage_dir, content, filename)
    await store_publication(db_session, book, read_publication(content), filename)


async def serve_every_manifest_href(
    client: AsyncClient, book_id: int
) -> list[tuple[dict[str, str], Response]]:
    """Fetch every file the manifest names, paired with the link that named it.

    A manifest that advertises an href this endpoint will not serve is the
    failure the two of them can only have together, so the manifest is what
    drives the requests rather than a list copied out of it.
    """
    manifest = (await client.get(manifest_url(book_id))).json()
    links: list[dict[str, str]] = manifest["readingOrder"] + manifest["resources"]
    return [
        (link, await client.get(resource_url(book_id, link["href"].removeprefix("resources/"))))
        for link in links
    ]


def member_bytes(epub_content: bytes, name: str) -> bytes:
    """What the archive really holds under ``name``, to compare a response against."""
    with zipfile.ZipFile(BytesIO(epub_content)) as archive:
        return archive.read(name)


@pytest.fixture
async def nested_toc_book(
    db_session: AsyncSession, test_book: models.Book, storage_dir: Path
) -> models.Book:
    """A book whose EPUB has awkward file names, styles and an image."""
    await store_indexed_epub(db_session, test_book, storage_dir, fixture_bytes("nested_toc"))
    return test_book


class TestServingPublicationFiles:
    """What GET /api/v1/readium/books/{id}/resources/{path} returns for a real book."""

    async def test_serves_a_chapter_unchanged(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should return the archive's own bytes under the declared media type."""
        response = await client.get(resource_url(nested_toc_book.id, CHAPTER_1))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.content == member_bytes(
            fixture_bytes("nested_toc"), "EPUB/text/chapter 1.xhtml"
        )
        assert b"<html" in response.content
        assert response.headers["content-type"] == "application/xhtml+xml"
        assert response.headers["cache-control"] == "private"

    async def test_serves_a_stylesheet(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should serve a supporting resource, not only the reading order."""
        response = await client.get(resource_url(nested_toc_book.id, STYLESHEET))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "text/css"
        assert response.content == member_bytes(fixture_bytes("nested_toc"), "EPUB/styles/main.css")

    async def test_serves_a_png_byte_for_byte(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should not re-encode binary content on its way out."""
        response = await client.get(resource_url(nested_toc_book.id, COVER_ART))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert response.content == member_bytes(
            fixture_bytes("nested_toc"), "EPUB/images/cover art.png"
        )

    async def test_serves_a_name_with_non_ascii_letters(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should reach a UTF-8 file name through its percent-encoded href."""
        response = await client.get(resource_url(nested_toc_book.id, CHAPTER_AANI))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.content == member_bytes(
            fixture_bytes("nested_toc"), "EPUB/text/luku-ääni.xhtml"
        )

    async def test_serves_a_file_whose_name_contains_a_percent_sign(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        storage_dir: Path,
    ) -> None:
        """Should decode the path exactly once, reaching the file that exists.

        The publication's one chapter is really named ``chapter%20one.xhtml``,
        so the manifest publishes ``chapter%2520one.xhtml``. Decoding that twice
        would name ``chapter one.xhtml``, which no EPUB here contains -- the
        request would 404 while the manifest kept advertising the href.
        """
        await store_indexed_epub(db_session, test_book, storage_dir, LITERAL_PERCENT_EPUB)

        response = await client.get(resource_url(test_book.id, "chapter%2520one.xhtml"))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "application/xhtml+xml"
        assert response.content == member_bytes(LITERAL_PERCENT_EPUB, "chapter%20one.xhtml")

    async def test_the_manifests_hrefs_all_resolve(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should serve every file the manifest names, with the type it named."""
        served = await serve_every_manifest_href(client, nested_toc_book.id)
        assert len(served) == 5

        for link, response in served:
            assert response.status_code == status.HTTP_200_OK, link["href"]
            assert response.headers["content-type"] == link["type"], link["href"]
            assert response.content, link["href"]

    async def test_an_index_that_cannot_be_stored_is_a_server_fault(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        storage_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should answer 500 rather than 404 when the derived index cannot be kept.

        Serving a file needs the row, which a book uploaded before indexes
        existed only gets on first read. The book is whole -- the manifest still
        renders it -- so a 404 would tell the reader its book had gone missing.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("nested_toc"))

        async def failing_save(*_args: object, **_kwargs: object) -> None:
            raise OperationalError("INSERT INTO book_publications", {}, Exception("locked"))

        monkeypatch.setattr(PublicationRepository, "save", failing_save)

        response = await client.get(resource_url(test_book.id, CHAPTER_1))
        manifest = await client.get(manifest_url(test_book.id))

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
        assert manifest.status_code == status.HTTP_200_OK, manifest.text


class TestServedResourcesCarryASandboxPolicy:
    """The policy that makes a resource harmless when a browser loads it directly."""

    async def test_a_chapter_is_served_under_a_sandbox_policy(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should send the policy with the markup the reader's frames are built from."""
        response = await client.get(resource_url(nested_toc_book.id, CHAPTER_1))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-security-policy"] == "sandbox"
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_the_app_wide_policy_does_not_overwrite_it(
        self,
        client: AsyncClient,
        nested_toc_book: models.Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should keep the resource's own policy where the app sets one of its own.

        ``SecurityHeadersMiddleware`` sends the app's policy outside development,
        and ``MutableHeaders`` assignment replaces rather than appends -- so a
        middleware that did not defer would quietly widen this endpoint back to
        ``script-src 'self'`` in every environment that matters, and only there.
        """
        monkeypatch.setattr(main_settings, "ENVIRONMENT", "production")

        resource = await client.get(resource_url(nested_toc_book.id, CHAPTER_1))
        manifest = await client.get(manifest_url(nested_toc_book.id))

        assert resource.headers["content-security-policy"] == "sandbox"
        # The app policy still reaches a response that expresses none of its own.
        assert "default-src 'self'" in manifest.headers["content-security-policy"]

    async def test_the_app_policy_lets_the_reader_frame_its_own_documents(
        self,
        client: AsyncClient,
        nested_toc_book: models.Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should not forbid this page from framing the reader's blob documents.

        Chromium does not apply an inherited ``frame-ancestors`` to blob
        children, so no desktop run ever reaches this.
        """
        monkeypatch.setattr(main_settings, "ENVIRONMENT", "production")

        manifest = await client.get(manifest_url(nested_toc_book.id))

        policy = manifest.headers["content-security-policy"]
        assert "frame-ancestors 'self'" in policy
        assert "frame-src 'self' blob:" in policy
        assert "script-src 'self' blob:" in policy
        assert "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com blob:" in policy


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
        self, client: AsyncClient, nested_toc_book: models.Book, path: str, why: str
    ) -> None:
        """Should serve only what the manifest advertises, whatever else the zip holds."""
        response = await client.get(resource_url(nested_toc_book.id, path))

        assert response.status_code == status.HTTP_404_NOT_FOUND, why

    @pytest.mark.parametrize(
        "path",
        [
            "..%2F..%2Fmanifest.json",
            "..%2F..%2F..%2F..%2Fetc%2Fpasswd",
            "/etc/passwd",
            "EPUB%2F..%2F..%2Fmanifest.json",
        ],
    )
    async def test_a_path_climbing_out_of_the_container_is_not_found(
        self, client: AsyncClient, nested_toc_book: models.Book, path: str
    ) -> None:
        """Should never resolve a path outside the publication, encoded or not.

        The membership check is the guard: the manifest's hrefs are already
        known not to escape the container, so nothing that escapes can be in the
        list, and there is no second normalisation step to get wrong.
        """
        response = await client.get(resource_url(nested_toc_book.id, path))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    async def test_another_users_publication_is_not_found(
        self, client: AsyncClient, db_session: AsyncSession, storage_dir: Path
    ) -> None:
        """Should refuse a book the caller does not own, index row and EPUB and all."""
        theirs = await another_users_book(db_session)
        await store_indexed_epub(db_session, theirs, storage_dir, fixture_bytes("nested_toc"))

        response = await client.get(resource_url(theirs.id, CHAPTER_1))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    async def test_a_media_type_that_is_not_one_is_not_echoed_back(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        storage_dir: Path,
    ) -> None:
        """Should not put a package document's text into a header unaltered.

        The media type is copied from a file the user uploaded. A value with a
        newline in it would smuggle a second header into the response, so
        anything that is not a plain ``type/subtype`` is replaced by one the
        browser will not act on.
        """
        await store_indexed_epub(
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

        response = await client.get(resource_url(test_book.id, "c1.xhtml"))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.headers["content-type"] == "application/octet-stream"


def one_chapter_epub(toc_title: str) -> bytes:
    """A publication whose one chapter is fixed and whose book's bytes are not.

    The chapter is identical across titles, so a reader holding it is only
    re-served if the tag follows the book rather than the member.
    """
    return build_epub(
        manifest_items='<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>',
        spine='<itemref idref="c1"/>',
        nav_links=f'<li><a href="c1.xhtml">{toc_title}</a></li>',
        files=("c1.xhtml",),
    )


class TestConditionalRequests:
    """The entity tag, and what a reader that already holds a file is told."""

    async def test_a_matching_if_none_match_is_answered_304(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should send the headers and no body when the caller's copy is current."""
        etag = (await client.get(resource_url(nested_toc_book.id, CHAPTER_1))).headers["etag"]

        response = await client.get(
            resource_url(nested_toc_book.id, CHAPTER_1), headers={"If-None-Match": etag}
        )

        assert response.status_code == status.HTTP_304_NOT_MODIFIED
        assert response.content == b""
        assert response.headers["etag"] == etag
        assert etag.startswith('"'), "a weak response tag would still match itself"
        assert response.headers["cache-control"] == "private"
        assert response.headers["content-security-policy"] == "sandbox"

    async def test_a_weak_validator_still_matches(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should compare tags weakly, as RFC 9110 requires for a GET."""
        etag = (await client.get(resource_url(nested_toc_book.id, CHAPTER_1))).headers["etag"]

        response = await client.get(
            resource_url(nested_toc_book.id, CHAPTER_1), headers={"If-None-Match": f"W/{etag}"}
        )

        assert response.status_code == status.HTTP_304_NOT_MODIFIED

    async def test_a_stale_if_none_match_is_answered_with_the_file(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should serve the file when the caller holds some other version."""
        response = await client.get(
            resource_url(nested_toc_book.id, CHAPTER_1),
            headers={"If-None-Match": '"not-the-one-we-serve"'},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.content

    async def test_a_wildcard_validator_matches(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should read a lone ``*`` as any current representation (RFC 9110 §13.1.2)."""
        response = await client.get(
            resource_url(nested_toc_book.id, CHAPTER_1), headers={"If-None-Match": "*"}
        )

        assert response.status_code == status.HTTP_304_NOT_MODIFIED

    async def test_a_quoted_star_is_a_tag_rather_than_the_wildcard(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should serve the file to a caller holding the entity-tag ``"*"``.

        ``*`` is a legal entity-tag character, so a wildcard carried inside the
        set of known versions would be indistinguishable from this tag.
        """
        response = await client.get(
            resource_url(nested_toc_book.id, CHAPTER_1), headers={"If-None-Match": '"*"'}
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.content

    async def test_the_etag_changes_when_the_books_epub_is_replaced(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        storage_dir: Path,
    ) -> None:
        """Should re-tag a chapter whose own bytes are unchanged but whose book's are not."""
        await store_indexed_epub(db_session, test_book, storage_dir, one_chapter_epub("One"))
        before = await client.get(resource_url(test_book.id, "c1.xhtml"))

        await store_indexed_epub(db_session, test_book, storage_dir, one_chapter_epub("Two"))
        after = await client.get(
            resource_url(test_book.id, "c1.xhtml"),
            headers={"If-None-Match": before.headers["etag"]},
        )

        assert after.status_code == status.HTTP_200_OK, after.text
        assert after.content == before.content
        assert after.headers["etag"] != before.headers["etag"]

    @pytest.mark.parametrize(
        ("validator", "why"),
        [
            ("{version}", "a bare token is not an entity-tag"),
            ('"x", *', "`*` is only a wildcard on its own"),
        ],
    )
    async def test_a_malformed_validator_does_not_match(
        self, client: AsyncClient, nested_toc_book: models.Book, validator: str, why: str
    ) -> None:
        """Should serve the file when the validator is not an entity-tag.

        RFC 9110 §8.8.3 spells an entity-tag as an optionally ``W/``-prefixed
        *quoted* string, so unwrapping optional quotes instead of reading the
        grammar would tell a client that dropped them its copy was current.
        """
        etag = (await client.get(resource_url(nested_toc_book.id, CHAPTER_1))).headers["etag"]
        malformed = validator.format(version=etag.strip('"'))
        assert malformed != etag

        response = await client.get(
            resource_url(nested_toc_book.id, CHAPTER_1), headers={"If-None-Match": malformed}
        )

        assert response.status_code == status.HTTP_200_OK, why
        assert response.content

    async def test_a_conditional_request_reads_no_file(
        self,
        client: AsyncClient,
        nested_toc_book: models.Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should answer 304 without fetching the EPUB at all.

        Only the ordering of the version check against the file read separates
        the two from outside, so the spy is the assertion.
        """
        etag = (await client.get(resource_url(nested_toc_book.id, CHAPTER_1))).headers["etag"]
        calls: list[str | None] = []
        original = FileRepository.get_epub

        async def counting(self: FileRepository, filename: str | None) -> bytes | None:
            calls.append(filename)
            return await original(self, filename)

        monkeypatch.setattr(FileRepository, "get_epub", counting)

        response = await client.get(
            resource_url(nested_toc_book.id, CHAPTER_1), headers={"If-None-Match": etag}
        )

        assert response.status_code == status.HTTP_304_NOT_MODIFIED
        assert calls == []

    async def test_a_path_the_publication_does_not_list_is_not_found_however_it_is_asked_for(
        self, client: AsyncClient, nested_toc_book: models.Book
    ) -> None:
        """Should 404 a path the manifest omits even to a caller holding the book's tag.

        A precondition narrows a request that would otherwise succeed (RFC 9110
        §13.2); it must not turn a refusal into "your copy is current".
        """
        etag = (await client.get(resource_url(nested_toc_book.id, CHAPTER_1))).headers["etag"]

        response = await client.get(
            resource_url(nested_toc_book.id, "EPUB/package.opf"), headers={"If-None-Match": etag}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
