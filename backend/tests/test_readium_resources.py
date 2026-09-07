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

import struct
import zipfile
import zlib
from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.web_reader.queries import publication_resource_query
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


def crc32_twin(payload: bytes) -> bytes:
    """Different bytes of the same length with the same CRC-32.

    CRC-32 is affine over GF(2) -- ``crc(x) = A(x) ^ crc(0)`` for a linear
    ``A`` -- so two equal-length messages collide exactly when their difference
    lies in ``A``'s kernel. Thirty-three single-bit differences are necessarily
    dependent in a 32-bit space, so eliminating them against each other finds a
    kernel vector to XOR in. Forging one is this cheap, which is the whole point
    of the tests below: a CRC is a transmission check, never an identity.
    """
    length = len(payload)
    assert length >= 5, "needs five bytes to hold thirty-three differing bits"
    zero = zlib.crc32(bytes(length))
    pivots: dict[int, tuple[int, int]] = {}

    for bit in range(33):
        probe = bytearray(length)
        probe[bit // 8] |= 1 << (bit % 8)
        delta = zlib.crc32(bytes(probe)) ^ zero
        used = 1 << bit
        while delta:
            high = delta.bit_length() - 1
            if high not in pivots:
                pivots[high] = (delta, used)
                break
            other_delta, other_used = pivots[high]
            delta ^= other_delta
            used ^= other_used
        else:
            mask = bytearray(length)
            for i in range(33):
                if used >> i & 1:
                    mask[i // 8] ^= 1 << (i % 8)
            twin = bytes(b ^ m for b, m in zip(payload, mask, strict=True))
            assert twin != payload
            assert zlib.crc32(twin) == zlib.crc32(payload)
            return twin

    raise AssertionError("no CRC-32 collision found")


# Two resources that are both empty, and so share a CRC-32 of zero. Anything
# that tells them apart has to be reading more than the checksum.
TWIN_EMPTY_MEMBERS_EPUB = build_epub(
    manifest_items=(
        '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="a" href="a.css" media-type="text/css"/>'
        '<item id="b" href="b.css" media-type="text/css"/>'
    ),
    spine='<itemref idref="c1"/>',
    nav_links='<li><a href="c1.xhtml">One</a></li>',
    files=("c1.xhtml", "a.css", "b.css"),
    bodies={"a.css": b"", "b.css": b""},
)


def understating_epub(member: str, real_size: int) -> bytes:
    """An EPUB whose one resource inflates far past the size it declares.

    Both the local header and the central directory are rewritten, so nothing
    short of decompressing the member can tell how big it really is. This is the
    shape a decompression bomb takes once a size cap exists to get past.
    """
    epub = bytearray(
        build_epub(
            manifest_items=(
                '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="big" href="big.css" media-type="text/css"/>'
            ),
            spine='<itemref idref="c1"/>',
            nav_links='<li><a href="c1.xhtml">One</a></li>',
            files=("c1.xhtml", member),
            bodies={member: b"A" * real_size},
            compression=zipfile.ZIP_DEFLATED,
        )
    )
    for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        struct.pack_into("<I", epub, epub.rfind(signature) + offset, 8)
    return bytes(epub)


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


class TestTheEtagIdentifiesTheBytes:
    """An entity tag has to name the representation, not merely a checksum of it."""

    async def test_two_empty_members_do_not_share_an_etag(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should tell two files apart even when their contents check out the same.

        Two empty files have the same CRC-32, so a tag built from the checksum
        alone is the same tag for both. A reader that had fetched one would then
        be told its copy of the *other* was current.
        """
        await store_epub(db_session, test_book, storage_dir, TWIN_EMPTY_MEMBERS_EPUB)

        first = await client.get(resource_url(test_book, "a.css"))
        second = await client.get(resource_url(test_book, "b.css"))

        assert first.status_code == second.status_code == status.HTTP_200_OK
        assert first.headers["etag"] != second.headers["etag"]

    async def test_one_members_etag_does_not_satisfy_another(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should not answer 304 to a tag that was issued for a different file."""
        await store_epub(db_session, test_book, storage_dir, TWIN_EMPTY_MEMBERS_EPUB)
        for_a = (await client.get(resource_url(test_book, "a.css"))).headers["etag"]

        response = await client.get(
            resource_url(test_book, "b.css"), headers={"If-None-Match": for_a}
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_a_replacement_member_with_a_forged_crc_still_retags(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should re-tag a replaced EPUB even when the member looks identical.

        A re-upload keeps the storage filename, so the name cannot say the bytes
        changed. Nor can the member's own central-directory record: forging a
        CRC-32 at a fixed length is arithmetic, so a replacement can present the
        same path, the same declared size and the same checksum over different
        content. Serving the old bytes from a reader's cache for as long as it
        keeps them is the failure this rules out.
        """
        original = b"body{color:red}"
        twin = crc32_twin(original)

        def epub_with(style: bytes) -> bytes:
            return build_epub(
                manifest_items=(
                    '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                    '<item id="s" href="style.css" media-type="text/css"/>'
                ),
                spine='<itemref idref="c1"/>',
                nav_links='<li><a href="c1.xhtml">One</a></li>',
                files=("c1.xhtml", "style.css"),
                bodies={"style.css": style},
            )

        await store_epub(db_session, test_book, storage_dir, epub_with(original))
        before = await client.get(resource_url(test_book, "style.css"))

        # The same storage filename, as a real re-upload would reuse.
        await store_epub(db_session, test_book, storage_dir, epub_with(twin))
        after = await client.get(resource_url(test_book, "style.css"))

        assert before.content == original
        assert after.content == twin
        assert after.content != before.content
        assert after.headers["etag"] != before.headers["etag"]

        stale = await client.get(
            resource_url(test_book, "style.css"),
            headers={"If-None-Match": before.headers["etag"]},
        )
        assert stale.status_code == status.HTTP_200_OK
        assert stale.content == twin


class TestDecompressionIsBounded:
    """A publication is a file the user uploaded, so its members are not read on trust."""

    async def test_refuses_a_member_larger_than_the_cap(
        self,
        client: AsyncClient,
        nested_toc_book: Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should turn away an oversized member rather than decompress it.

        The cap is lowered rather than the fixture inflated: a real member big
        enough to trip the limit would only make the test slow.
        """
        monkeypatch.setattr(publication_resource_query, "MAX_RESOURCE_BYTES", 10)

        response = await client.get(resource_url(nested_toc_book, CHAPTER_1))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_refuses_a_member_that_understates_its_size(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
    ) -> None:
        """Should refuse a member that lies about its size rather than serve it.

        This is the outcome only. What the endpoint spends getting there is not
        visible from out here, because the shared parser reads every manifest
        item before this endpoint sees one -- see
        ``tests/unit/infrastructure/web_reader/test_publication_resource_query.py``
        for the assertion about the bytes this endpoint's own read allocates.
        """
        await store_epub(
            db_session, test_book, storage_dir, understating_epub("big.css", 1024 * 1024)
        )

        response = await client.get(resource_url(test_book, "big.css"))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.content) < 1024

    async def test_a_conditional_request_decompresses_nothing(
        self,
        client: AsyncClient,
        nested_toc_book: Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should answer 304 without reading the member at all.

        Everything the tag is made of comes from the archive's directory, so a
        reader that already holds a file should cost no decompression. Only the
        ordering separates the two from outside, so the spy is the assertion.
        """
        etag = (await client.get(resource_url(nested_toc_book, CHAPTER_1))).headers["etag"]
        reads: list[str] = []

        def refuse(archive: object, entry: zipfile.ZipInfo) -> bytes:
            reads.append(entry.filename)
            raise AssertionError("decompressed a member to answer a conditional request")

        monkeypatch.setattr(publication_resource_query, "read_bounded_member", refuse)

        response = await client.get(
            resource_url(nested_toc_book, CHAPTER_1), headers={"If-None-Match": etag}
        )

        assert response.status_code == status.HTTP_304_NOT_MODIFIED
        assert response.content == b""
        assert reads == []

    async def test_the_size_policy_outranks_a_precondition(
        self,
        client: AsyncClient,
        nested_toc_book: Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should refuse an unservable member even to a caller that would take a 304.

        A precondition narrows a request that would otherwise succeed (RFC 9110
        §13.2). It cannot make one succeed that would not, so ``If-None-Match: *``
        must not turn a refusal into "your copy is current" -- which would leave
        a reader believing a file it can never fetch is up to date.
        """
        monkeypatch.setattr(publication_resource_query, "MAX_RESOURCE_BYTES", 10)

        response = await client.get(
            resource_url(nested_toc_book, CHAPTER_1), headers={"If-None-Match": "*"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "template",
        [
            "{version}",
            "W/{version}",
            '"{version}',
            '{version}"',
            "'{version}'",
        ],
    )
    async def test_a_malformed_validator_does_not_match(
        self, client: AsyncClient, nested_toc_book: Book, template: str
    ) -> None:
        """Should serve the file when the validator is not an entity-tag.

        RFC 9110 §8.8.3 spells an entity-tag as an optionally ``W/``-prefixed
        *quoted* string. Unwrapping optional quotes instead of reading the
        grammar would let a bare token match, so a client that dropped the
        quotes would be told its copy was current on the strength of a header
        the standard does not define.
        """
        etag = (await client.get(resource_url(nested_toc_book, CHAPTER_1))).headers["etag"]
        malformed = template.format(version=etag.strip('"'))
        assert malformed != etag

        response = await client.get(
            resource_url(nested_toc_book, CHAPTER_1), headers={"If-None-Match": malformed}
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
