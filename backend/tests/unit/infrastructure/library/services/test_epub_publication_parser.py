"""Tests for reading an EPUB into the index a Readium manifest is rendered from.

The hrefs asserted here are the same strings a derived Locator will carry for
the same file: relative to the EPUB container root, percent-encoded exactly
once. A highlight cannot be anchored to a resource the index names differently.
"""

import hashlib
import io
import struct
import tracemalloc
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.publications import PublicationResource
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.library.services import epub_publication_parser
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.library.services.epub_publication_parser import read_publication

_: PublicationParserProtocol = EpubParserService()

MINIMAL_EPUB = Path(__file__).parents[4] / "fixtures" / "minimal.epub"

DEFAULT_IDENTIFIERS = '<dc:identifier id="bookid">urn:uuid:hand-built</dc:identifier>'
DOCUMENT = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page</title></head>'
    b"<body><p>Hi there.</p></body></html>"
)


def container_xml(rootfile: str = '<rootfile full-path="content.opf"/>') -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        f"<rootfiles>{rootfile}</rootfiles></container>"
    )


def build_epub(
    manifest_items: str,
    spine: str,
    files: tuple[str, ...] = (),
    unique_identifier: str = "bookid",
    identifiers: str = DEFAULT_IDENTIFIERS,
    extra_metadata: str = "",
    opf_name: str = "content.opf",
    container: str | None = None,
) -> bytes:
    """Assemble an EPUB by hand, so a broken or hostile one reads as such in the diff.

    What the archive really holds (``files``) is deliberately separate from what
    the manifest promises (``manifest_items``): a manifest naming a file that is
    not there is one of the shapes under test.
    """
    package = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        f'unique-identifier="{unique_identifier}">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"{identifiers}<dc:title>Hand Built</dc:title><dc:language>en</dc:language>"
        f"{extra_metadata}</metadata>"
        f"<manifest>{manifest_items}</manifest><spine>{spine}</spine></package>"
    )

    out = BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            container
            if container is not None
            else container_xml(f'<rootfile full-path="{opf_name}"/>'),
        )
        archive.writestr(opf_name, package)
        for name in files:
            archive.writestr(name, DOCUMENT)
    return out.getvalue()


def hrefs(resources: tuple[PublicationResource, ...]) -> list[str]:
    return [resource.href for resource in resources]


class TestAnEpubBecomesAPublicationIndex:
    """The ordinary book, read end to end through the service that publishes it."""

    def test_a_real_epub_resolves_to_its_reading_order_resources_and_metadata(self) -> None:
        # Sizes come from the archive rather than the package document, which
        # states none: a conditional request's Content-Length is computed from them.
        content = MINIMAL_EPUB.read_bytes()

        publication = EpubParserService().parse_publication(content)

        assert publication.metadata.title == "The Lantern Fixture"
        assert publication.metadata.language == "en"
        assert publication.metadata.identifier == "urn:uuid:8f1a0c2e-0000-4000-8000-000000000001"
        assert publication.metadata.author is None
        assert hrefs(publication.reading_order) == [
            "OEBPS/chapter1.xhtml",
            "OEBPS/chapter2.xhtml",
        ]
        assert [item.size for item in publication.reading_order] == [447, 336]
        assert hrefs(publication.resources) == ["OEBPS/nav.xhtml"]
        assert publication.resources[0].size == 376
        assert publication.content_hash == hashlib.sha256(content).hexdigest()
        assert publication.toc == ()

    def test_bytes_that_are_not_an_archive_at_all_are_not_a_readable_epub(self) -> None:
        with pytest.raises(InvalidEbookError):
            read_publication(b"not a zip")

    def test_an_archive_without_a_container_is_refused_by_the_member_it_lacks(self) -> None:
        out = BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("content.opf", "<package/>")

        with pytest.raises(InvalidEbookError, match=r"META-INF/container\.xml"):
            read_publication(out.getvalue())

    def test_a_container_naming_no_package_document_is_refused(self) -> None:
        content = build_epub(
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>',
            '<itemref idref="ch1"/>',
            files=("chapter1.xhtml",),
            container=container_xml('<rootfile media-type="application/oebps-package+xml"/>'),
        )

        with pytest.raises(InvalidEbookError, match="names no package document"):
            read_publication(content)


class TestThePublishedIdentifierIsTheDesignatedOne:
    """A book carries several identifiers and says which one it *is*."""

    IDENTIFIERS = (
        '<dc:identifier id="isbn">urn:isbn:9780000000001</dc:identifier>'
        '<dc:identifier id="uuid">urn:uuid:designated</dc:identifier>'
    )
    MANIFEST = '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'

    def test_the_identifier_the_package_designates_is_published(self) -> None:
        content = build_epub(
            self.MANIFEST,
            '<itemref idref="ch1"/>',
            files=("chapter1.xhtml",),
            unique_identifier="uuid",
            identifiers=self.IDENTIFIERS,
        )

        assert read_publication(content).metadata.identifier == "urn:uuid:designated"

    def test_a_designation_naming_nothing_falls_back_to_the_first_identifier(self) -> None:
        # The identity a reader stores its state under must not change between
        # two parses of the same file, so the fallback is never invented.
        content = build_epub(
            self.MANIFEST,
            '<itemref idref="ch1"/>',
            files=("chapter1.xhtml",),
            unique_identifier="absent",
            identifiers=self.IDENTIFIERS,
        )

        assert read_publication(content).metadata.identifier == "urn:isbn:9780000000001"


class TestAnHrefNamesTheFileTheArchiveHolds:
    """An href is encoded once, from the name the archive really uses.

    The manifest writes a file's name encoded and the archive stores it raw, so
    a size looked up under the wrong one of the two silently finds nothing.
    """

    def test_a_name_needing_encoding_is_published_encoded_and_still_sized(self) -> None:
        content = build_epub(
            '<item id="ch1" href="OEBPS/chapter%20one.xhtml" media-type="application/xhtml+xml"/>',
            '<itemref idref="ch1"/>',
            files=("OEBPS/chapter one.xhtml",),
        )

        publication = read_publication(content)

        assert hrefs(publication.reading_order) == ["OEBPS/chapter%20one.xhtml"]
        assert publication.reading_order[0].size == len(DOCUMENT)

    def test_a_name_really_containing_a_percent_sign_survives_the_round_trip(self) -> None:
        # Decoding twice would name ``chapter one.xhtml``, a file the archive
        # does not hold.
        content = build_epub(
            '<item id="ch1" href="a%2520b.xhtml" media-type="application/xhtml+xml"/>',
            '<itemref idref="ch1"/>',
            files=("a%20b.xhtml",),
        )

        assert hrefs(read_publication(content).reading_order) == ["a%2520b.xhtml"]


class TestAManifestOnlyPromisesFilesTheServerCanServe:
    """An item the server could not answer for is dropped rather than published."""

    def test_an_item_the_archive_does_not_hold_is_dropped(self) -> None:
        content = build_epub(
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="ghost" href="chapter2.xhtml" media-type="application/xhtml+xml"/>',
            '<itemref idref="ch1"/><itemref idref="ghost"/>',
            files=("chapter1.xhtml",),
        )

        assert hrefs(read_publication(content).reading_order) == ["chapter1.xhtml"]

    def test_an_item_naming_no_file_at_all_is_dropped(self) -> None:
        content = build_epub(
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="nameless" media-type="text/css"/>',
            '<itemref idref="ch1"/>',
            files=("chapter1.xhtml",),
        )

        publication = read_publication(content)

        assert hrefs(publication.reading_order) == ["chapter1.xhtml"]
        assert publication.resources == ()

    def test_a_spine_emptied_by_missing_files_is_an_unopenable_book(self) -> None:
        content = build_epub(
            '<item id="ghost" href="chapter1.xhtml" media-type="application/xhtml+xml"/>',
            '<itemref idref="ghost"/>',
        )

        with pytest.raises(InvalidEbookError):
            read_publication(content)


class TestNoHrefLeavesTheContainer:
    """A path that escapes is refused wherever it comes from: the item or the rootfile.

    The archive really carries members under the escaping names, so being
    present is not what saves an item: only refusing the path keeps it out.
    """

    def test_an_item_pointing_outside_the_container_is_dropped(self) -> None:
        content = build_epub(
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="climb" href="../secrets.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="root" href="/secrets.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="style" href="style.css" media-type="text/css"/>',
            '<itemref idref="ch1"/>',
            files=("chapter1.xhtml", "style.css", "../secrets.xhtml", "/secrets.xhtml"),
        )

        publication = read_publication(content)

        assert hrefs(publication.reading_order) == ["chapter1.xhtml"]
        assert hrefs(publication.resources) == ["style.css"]

    def test_an_item_climbing_to_the_container_root_is_published(self) -> None:
        content = build_epub(
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="style" href="../style.css" media-type="text/css"/>',
            '<itemref idref="ch1"/>',
            files=("OEBPS/chapter1.xhtml", "style.css"),
            opf_name="OEBPS/content.opf",
        )

        publication = read_publication(content)

        assert hrefs(publication.reading_order) == ["OEBPS/chapter1.xhtml"]
        assert hrefs(publication.resources) == ["style.css"]

    def test_a_rootfile_rooting_the_package_at_a_double_slash_publishes_nothing(self) -> None:
        # The rootfile decides where every href resolves, so rooted at ``//``
        # every one of them is protocol-relative -- a URL a browser resolves
        # against another host -- and none of them survives to be published.
        manifest = (
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="style" href="style.css" media-type="text/css"/>'
        )
        at_the_root = build_epub(
            manifest, '<itemref idref="ch1"/>', files=("chapter1.xhtml", "style.css")
        )
        assert hrefs(read_publication(at_the_root).reading_order) == ["chapter1.xhtml"]

        protocol_relative = build_epub(
            manifest,
            '<itemref idref="ch1"/>',
            files=("//chapter1.xhtml", "//style.css"),
            opf_name="//content.opf",
        )

        with pytest.raises(InvalidEbookError, match="no readable spine items"):
            read_publication(protocol_relative)


class TestAResourceIsPublishedUnderAUsableMediaType:
    """Every resource carries a media type, whatever the package document manages."""

    MANIFEST = '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
    SPINE = '<itemref idref="ch1"/>'

    def test_a_mistyped_jpeg_is_corrected(self) -> None:
        content = build_epub(
            f'{self.MANIFEST}<item id="cover" href="cover.jpg" media-type="image/jpg"/>',
            self.SPINE,
            files=("chapter1.xhtml", "cover.jpg"),
        )

        assert read_publication(content).resources[0].media_type == "image/jpeg"

    def test_an_item_declaring_no_media_type_is_guessed_from_its_extension(self) -> None:
        content = build_epub(
            f'{self.MANIFEST}<item id="style" href="style.css"/>',
            self.SPINE,
            files=("chapter1.xhtml", "style.css"),
        )

        assert read_publication(content).resources[0].media_type == "text/css"


class TestAStructuralDocumentCostsWhatItDeclares:
    """The package document is the one member the parse cannot skip."""

    BOMB_SIZE = 64 * 1024 * 1024

    def test_a_package_document_over_the_cap_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        content = build_epub(
            '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>',
            '<itemref idref="ch1"/>',
            files=("chapter1.xhtml",),
            extra_metadata=f"<dc:description>{'padding ' * 200}</dc:description>",
        )
        monkeypatch.setattr(epub_publication_parser, "MAX_STRUCTURAL_DOCUMENT_BYTES", 1000)

        with pytest.raises(InvalidEbookError):
            read_publication(content)

    def test_a_package_document_that_understates_its_size_is_not_inflated(self) -> None:
        # The cap alone cannot do this: a member declaring eight bytes passes it
        # and then costs the 64 MiB anyway, because ``ZipFile.read()`` truncates
        # its result to the declaration and hands the decompressor no limit.
        content = self._epub_understating_its_package(b"A" * self.BOMB_SIZE, declared=8)
        assert len(content) < 1024 * 1024, "the archive itself should be small"

        tracemalloc.start()
        try:
            with pytest.raises(InvalidEbookError):
                read_publication(content)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert peak < self.BOMB_SIZE // 8, f"inflated the member: {peak / 1024**2:.0f} MiB"

    @staticmethod
    def _epub_understating_its_package(body: bytes, declared: int) -> bytes:
        # Local header and central directory are patched alike, so no honest
        # copy of the number is left for the parse to prefer to the lie.
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("META-INF/container.xml", container_xml())
            archive.writestr("content.opf", body)

        content = bytearray(out.getvalue())
        for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
            struct.pack_into("<I", content, content.rfind(signature) + offset, declared)
        return bytes(content)
