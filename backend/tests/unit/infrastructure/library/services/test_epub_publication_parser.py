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
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path

import pytest

from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.publications import PublicationResource, TocEntry
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.library.services import epub_publication_parser
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.library.services.epub_publication_parser import read_publication

_: PublicationParserProtocol = EpubParserService()

FIXTURES = Path(__file__).parents[4] / "fixtures"
MINIMAL_EPUB = FIXTURES / "minimal.epub"
NESTED_TOC_EPUB = FIXTURES / "nested_toc.epub"

DEFAULT_IDENTIFIERS = '<dc:identifier id="bookid">urn:uuid:hand-built</dc:identifier>'
DOCUMENT = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page</title></head>'
    b"<body><p>Hi there.</p></body></html>"
)

CHAPTER_ITEM = '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
NAV_ITEM = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
NCX_ITEM = '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
CHAPTER_SPINE = '<itemref idref="ch1"/>'

BOMB_SIZE = 64 * 1024 * 1024


def container_xml(rootfile: str = '<rootfile full-path="content.opf"/>') -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        f"<rootfiles>{rootfile}</rootfiles></container>"
    )


def nav_document(
    list_items: str, attributes: str = 'epub:type="toc"', preceded_by: str = ""
) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
        "<head><title>Contents</title></head>"
        f"<body>{preceded_by}<nav {attributes}><ol>{list_items}</ol></nav></body></html>"
    )


def ncx_document(nav_points: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        f"<navMap>{nav_points}</navMap></ncx>"
    )


def nav_point(label: str, src: str, children: str = "") -> str:
    return (
        f"<navPoint><navLabel><text>{label}</text></navLabel>"
        f'<content src="{src}"/>{children}</navPoint>'
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
    spine_toc: str | None = None,
    documents: Mapping[str, str] | None = None,
) -> bytes:
    """Assemble an EPUB by hand, so a broken or hostile one reads as such in the diff.

    What the archive really holds (``files``, and ``documents`` for a member
    whose content matters) is deliberately separate from what the manifest
    promises: a manifest naming a file that is not there is one of the shapes
    under test.
    """
    package = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        f'unique-identifier="{unique_identifier}">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"{identifiers}<dc:title>Hand Built</dc:title><dc:language>en</dc:language>"
        f"{extra_metadata}</metadata>"
        f"<manifest>{manifest_items}</manifest>"
        f"<spine{f' toc="{spine_toc}"' if spine_toc is not None else ''}>{spine}</spine></package>"
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
        for name, content in (documents or {}).items():
            archive.writestr(name, content)
    return out.getvalue()


def epub_with_nav(nav: str) -> bytes:
    return build_epub(
        f"{CHAPTER_ITEM}{NAV_ITEM}",
        CHAPTER_SPINE,
        files=("chapter1.xhtml",),
        documents={"nav.xhtml": nav},
    )


def understating_its_last_member(content: bytes, declared: int) -> bytes:
    """Rewrite the size the archive's final member declares, leaving what it holds.

    Local header and central directory are patched alike, so no honest copy of
    the number is left for the parse to prefer to the lie.
    """
    patched = bytearray(content)
    for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        struct.pack_into("<I", patched, patched.rfind(signature) + offset, declared)
    return bytes(patched)


def hrefs(resources: tuple[PublicationResource, ...]) -> list[str]:
    return [resource.href for resource in resources]


def peak_bytes_refusing(content: bytes) -> int:
    """Refuse an archive and report what refusing it cost, in bytes."""
    tracemalloc.start()
    try:
        with pytest.raises(InvalidEbookError):
            read_publication(content)
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


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
        assert publication.toc == (
            TocEntry("Chapter One", "OEBPS/chapter1.xhtml"),
            TocEntry("Chapter Two", "OEBPS/chapter2.xhtml"),
        )

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

    def test_a_toc_entry_names_that_file_the_way_the_reading_order_does(self) -> None:
        # A navigation link arrives encoded and a manifest file name decoded, so
        # the two meet only if each is decoded exactly as many times as it was.
        content = build_epub(
            f'<item id="ch1" href="a%2520b.xhtml" media-type="application/xhtml+xml"/>{NAV_ITEM}',
            CHAPTER_SPINE,
            files=("a%20b.xhtml",),
            documents={
                "nav.xhtml": nav_document(
                    '<li><a href="a%2520b.xhtml#luku ääni">Luku Ääni</a></li>'
                )
            },
        )

        publication = read_publication(content)

        assert hrefs(publication.reading_order) == ["a%2520b.xhtml"]
        assert publication.toc == (TocEntry("Luku Ääni", "a%2520b.xhtml#luku%20%C3%A4%C3%A4ni"),)


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
        content = self._epub_understating_its_package(b"A" * BOMB_SIZE, declared=8)
        assert len(content) < 1024 * 1024, "the archive itself should be small"

        peak = peak_bytes_refusing(content)

        assert peak < BOMB_SIZE // 8, f"inflated the member: {peak / 1024**2:.0f} MiB"

    @staticmethod
    def _epub_understating_its_package(body: bytes, declared: int) -> bytes:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("META-INF/container.xml", container_xml())
            archive.writestr("content.opf", body)
        return understating_its_last_member(out.getvalue(), declared)


class TestAPublicationCarriesTheTableOfContentsItStates:
    """The navigation document, or the NCX behind it, read into nested entries."""

    def test_a_navigation_document_is_published_entry_for_entry(self) -> None:
        publication = EpubParserService().parse_publication(NESTED_TOC_EPUB.read_bytes())

        assert publication.metadata.title == "Kirjan Ääni"
        assert publication.toc == (
            TocEntry(
                title="Part One",
                href="EPUB/text/chapter%201.xhtml",
                children=(
                    TocEntry("Chapter One", "EPUB/text/chapter%201.xhtml#sec1"),
                    TocEntry("Luku Ääni", "EPUB/text/luku-%C3%A4%C3%A4ni.xhtml"),
                ),
            ),
            TocEntry("Appendix", "EPUB/text/luku-%C3%A4%C3%A4ni.xhtml#loppu"),
        )

    def test_a_publication_carrying_both_is_read_from_its_navigation_document(self) -> None:
        content = build_epub(
            f"{CHAPTER_ITEM}{NAV_ITEM}{NCX_ITEM}",
            CHAPTER_SPINE,
            files=("chapter1.xhtml",),
            spine_toc="ncx",
            documents={
                "nav.xhtml": nav_document('<li><a href="chapter1.xhtml">From the nav</a></li>'),
                "toc.ncx": ncx_document(nav_point("From the NCX", "chapter1.xhtml")),
            },
        )

        assert read_publication(content).toc == (TocEntry("From the nav", "chapter1.xhtml"),)

    def test_a_publication_stating_only_an_ncx_is_read_from_it(self) -> None:
        content = build_epub(
            f"{CHAPTER_ITEM}{NCX_ITEM}",
            CHAPTER_SPINE,
            files=("chapter1.xhtml",),
            spine_toc="ncx",
            documents={
                "toc.ncx": ncx_document(
                    nav_point(
                        "Part One",
                        "chapter1.xhtml",
                        nav_point("Chapter One", "chapter1.xhtml#sec1"),
                    )
                )
            },
        )

        assert read_publication(content).toc == (
            TocEntry(
                "Part One",
                "chapter1.xhtml",
                (TocEntry("Chapter One", "chapter1.xhtml#sec1"),),
            ),
        )

    def test_a_publication_stating_neither_carries_no_table_of_contents(self) -> None:
        content = build_epub(CHAPTER_ITEM, CHAPTER_SPINE, files=("chapter1.xhtml",))

        assert read_publication(content).toc == ()

    def test_a_spine_naming_an_empty_ncx_matches_no_item_at_all(self) -> None:
        # An item declaring no id carries the empty string, so an empty ``toc``
        # taken at face value would read the first of them as the NCX.
        content = build_epub(
            f'{CHAPTER_ITEM}<item href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            CHAPTER_SPINE,
            files=("chapter1.xhtml",),
            spine_toc="",
            documents={"toc.ncx": ncx_document(nav_point("From the NCX", "chapter1.xhtml"))},
        )

        assert read_publication(content).toc == ()

    def test_a_navigation_document_declaring_the_wrong_media_type_is_still_read(self) -> None:
        # ``properties="nav"`` names the navigation document by itself, and the
        # parse reads it as HTML whatever the manifest calls it.
        content = build_epub(
            f'{CHAPTER_ITEM}<item id="nav" href="nav.xhtml" media-type="text/html"'
            ' properties="nav"/>',
            CHAPTER_SPINE,
            files=("chapter1.xhtml",),
            documents={
                "nav.xhtml": nav_document('<li><a href="chapter1.xhtml">Chapter One</a></li>')
            },
        )

        assert read_publication(content).toc == (TocEntry("Chapter One", "chapter1.xhtml"),)

    def test_an_ncx_point_missing_its_label_or_its_target_still_takes_its_place(self) -> None:
        content = build_epub(
            f"{CHAPTER_ITEM}{NCX_ITEM}",
            CHAPTER_SPINE,
            files=("chapter1.xhtml",),
            spine_toc="ncx",
            documents={
                "toc.ncx": ncx_document(
                    '<navPoint><content src="chapter1.xhtml"/></navPoint>'
                    "<navPoint><navLabel><text>Nowhere</text></navLabel></navPoint>"
                )
            },
        )

        assert read_publication(content).toc == (
            TocEntry("", "chapter1.xhtml"),
            TocEntry("Nowhere", None),
        )

    def test_a_navigation_document_resolves_its_links_against_its_own_directory(self) -> None:
        content = build_epub(
            '<item id="ch1" href="text/chapter1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="nav" href="nav/toc.xhtml" media-type="application/xhtml+xml"'
            ' properties="nav"/>',
            CHAPTER_SPINE,
            files=("OEBPS/text/chapter1.xhtml",),
            opf_name="OEBPS/content.opf",
            documents={
                "OEBPS/nav/toc.xhtml": nav_document(
                    '<li><a href="../text/chapter1.xhtml">Chapter One</a></li>'
                )
            },
        )

        assert read_publication(content).toc == (
            TocEntry("Chapter One", "OEBPS/text/chapter1.xhtml"),
        )


class TestANavigationEntryNamesSomethingThePublicationHolds:
    """An entry that cannot point anywhere still says where it sits."""

    def test_an_entry_pointing_outside_the_container_keeps_its_title_and_children(self) -> None:
        content = epub_with_nav(
            nav_document(
                '<li><a href="../secrets.xhtml">Outside</a>'
                '<ol><li><a href="chapter1.xhtml">Inside</a></li></ol></li>'
            )
        )

        assert read_publication(content).toc == (
            TocEntry("Outside", None, (TocEntry("Inside", "chapter1.xhtml"),)),
        )

    def test_an_entry_linking_to_another_site_keeps_its_title_and_children(self) -> None:
        content = epub_with_nav(
            nav_document(
                '<li><a href="https://example.com/a.html">Elsewhere</a>'
                '<ol><li><a href="chapter1.xhtml">Inside</a></li></ol></li>'
            )
        )

        assert read_publication(content).toc == (
            TocEntry("Elsewhere", None, (TocEntry("Inside", "chapter1.xhtml"),)),
        )

    def test_an_entry_linking_only_to_a_fragment_links_nowhere(self) -> None:
        content = epub_with_nav(
            nav_document(
                '<li><a href="#sec1">Somewhere in here</a>'
                '<ol><li><a href="chapter1.xhtml">Inside</a></li></ol></li>'
            )
        )

        assert read_publication(content).toc == (
            TocEntry("Somewhere in here", None, (TocEntry("Inside", "chapter1.xhtml"),)),
        )

    def test_a_colon_after_the_first_path_segment_is_part_of_a_file_name(self) -> None:
        content = build_epub(
            f'<item id="ch1" href="text/a:b.xhtml" media-type="application/xhtml+xml"/>{NAV_ITEM}',
            CHAPTER_SPINE,
            files=("text/a:b.xhtml",),
            documents={
                "nav.xhtml": nav_document('<li><a href="text/a:b.xhtml">Chapter One</a></li>')
            },
        )

        assert read_publication(content).toc == (TocEntry("Chapter One", "text/a%3Ab.xhtml"),)

    def test_a_heading_over_other_entries_is_kept_and_a_line_naming_nothing_is_not(self) -> None:
        content = epub_with_nav(
            nav_document(
                "<li><span>Part One</span>"
                '<ol><li><a href="chapter1.xhtml">Chapter One</a></li></ol></li>'
                "<li>Front matter</li>"
            )
        )

        assert read_publication(content).toc == (
            TocEntry("Part One", None, (TocEntry("Chapter One", "chapter1.xhtml"),)),
        )


class TestTheMarkupAroundAnEntryDoesNotCostTheTableOfContents:
    """A navigation document is HTML, and carries whatever a publisher's toolchain left in it."""

    def test_a_comment_inside_an_entry_leaves_it_and_its_children_intact(self) -> None:
        content = epub_with_nav(
            nav_document(
                '<li><!-- generated --><a href="chapter1.xhtml">Part One</a>'
                '<ol><li><a href="chapter1.xhtml#sec1">Chapter One</a></li></ol></li>'
            )
        )

        assert read_publication(content).toc == (
            TocEntry(
                "Part One",
                "chapter1.xhtml",
                (TocEntry("Chapter One", "chapter1.xhtml#sec1"),),
            ),
        )

    def test_an_entry_holding_nothing_but_its_children_is_titled_by_nothing(self) -> None:
        content = epub_with_nav(
            nav_document('<li><ol><li><a href="chapter1.xhtml">Chapter One</a></li></ol></li>')
        )

        assert read_publication(content).toc == (
            TocEntry("", None, (TocEntry("Chapter One", "chapter1.xhtml"),)),
        )

    def test_a_navigation_type_naming_further_roles_still_names_the_table_of_contents(self) -> None:
        content = epub_with_nav(
            nav_document(
                '<li><a href="chapter1.xhtml">Chapter One</a></li>',
                attributes='epub:type="toc bodymatter"',
            )
        )

        assert read_publication(content).toc == (TocEntry("Chapter One", "chapter1.xhtml"),)

    def test_another_nav_answering_to_toc_first_does_not_win_over_the_stated_one(self) -> None:
        content = epub_with_nav(
            nav_document(
                '<li><a href="chapter1.xhtml">From the toc nav</a></li>',
                preceded_by=(
                    '<nav epub:type="landmarks" id="toc"><ol>'
                    '<li><a href="chapter1.xhtml">From the landmarks nav</a></li></ol></nav>'
                ),
            )
        )

        assert read_publication(content).toc == (TocEntry("From the toc nav", "chapter1.xhtml"),)


class TestNavigationThatCannotBeReadCostsTheTableOfContentsAlone:
    """A book whose navigation is broken is still a book a reader pages through."""

    def test_a_navigation_document_that_cannot_be_parsed_leaves_the_book_readable(self) -> None:
        content = epub_with_nav("")

        publication = read_publication(content)

        assert publication.toc == ()
        assert hrefs(publication.reading_order) == ["chapter1.xhtml"]

    def test_a_navigation_document_stating_no_table_of_contents_publishes_none(self) -> None:
        content = epub_with_nav(
            nav_document(
                '<li><a href="chapter1.xhtml">Start reading</a></li>',
                attributes='epub:type="landmarks"',
            )
        )

        publication = read_publication(content)

        assert publication.toc == ()
        assert hrefs(publication.reading_order) == ["chapter1.xhtml"]

    def test_a_navigation_document_the_archive_does_not_hold_leaves_the_book_readable(self) -> None:
        # An absent member is the same shape of broken as an unparseable one,
        # and the manifest drops the very item the spine here still needs.
        content = build_epub(
            f"{CHAPTER_ITEM}{NAV_ITEM}", CHAPTER_SPINE, files=("chapter1.xhtml",), documents={}
        )

        publication = read_publication(content)

        assert publication.toc == ()
        assert hrefs(publication.reading_order) == ["chapter1.xhtml"]
        assert hrefs(publication.resources) == []

    def test_a_navigation_document_that_understates_its_size_is_refused_uninflated(self) -> None:
        # Degrading past this one would mean paying for the bomb first: the
        # member is read before anything can tell that it is unparseable.
        out = io.BytesIO(
            build_epub(f"{CHAPTER_ITEM}{NAV_ITEM}", CHAPTER_SPINE, files=("chapter1.xhtml",))
        )
        with zipfile.ZipFile(out, "a", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("nav.xhtml", b"A" * BOMB_SIZE)
        content = understating_its_last_member(out.getvalue(), declared=8)
        assert len(content) < 1024 * 1024, "the archive itself should be small"

        peak = peak_bytes_refusing(content)

        assert peak < BOMB_SIZE // 8, f"inflated the member: {peak / 1024**2:.0f} MiB"
