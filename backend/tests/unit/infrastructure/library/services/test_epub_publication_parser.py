"""Tests for reading an EPUB into the index a Readium manifest is rendered from.

The hrefs asserted here are the same strings a derived Locator will carry for
the same file: relative to the EPUB container root, percent-encoded exactly
once. A highlight cannot be anchored to a resource the index names differently.
"""

import hashlib
import logging
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.publications import (
    PublicationLayout,
    PublicationResource,
    TocEntry,
)
from src.domain.library.entities.epub_metadata import EpubMetadata
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.library.services.epub_publication_parser import (
    read_epub_metadata,
    read_publication,
)
from tests.epub_builders import (
    DOCUMENT,
    NAV_ITEM,
    build_epub,
    container_xml,
    nav_document,
)

_: PublicationParserProtocol = EpubParserService()

FIXTURES = Path(__file__).parents[4] / "fixtures"
MINIMAL_EPUB = FIXTURES / "minimal.epub"
NESTED_TOC_EPUB = FIXTURES / "nested_toc.epub"
FIXED_LAYOUT_EPUB = FIXTURES / "fixed_layout.epub"

CHAPTER_ITEM = '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
NCX_ITEM = '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
CHAPTER_SPINE = '<itemref idref="ch1"/>'

EOCD_SIGNATURE = b"PK\x05\x06"


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


def epub_with_nav(nav: str) -> bytes:
    return build_epub(
        f"{CHAPTER_ITEM}{NAV_ITEM}",
        CHAPTER_SPINE,
        files=("chapter1.xhtml",),
        documents={"nav.xhtml": nav},
    )


def archive_of_empty_members(entries: int) -> bytes:
    """Build a real zip of empty members, so the trailer under test is one Python wrote."""
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as archive:
        for index in range(entries):
            archive.writestr(str(index), b"")
    return out.getvalue()


def hrefs(resources: tuple[PublicationResource, ...]) -> list[str]:
    return [resource.href for resource in resources]


def layouts(resources: tuple[PublicationResource, ...]) -> list[PublicationLayout | None]:
    return [resource.layout for resource in resources]


class TestAnEpubBecomesAPublicationIndex:
    """The ordinary book, read end to end through the service that publishes it, and
    the bytes that are not a book at all."""

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

    def test_an_archive_with_no_trailer_at_all_is_refused_by_the_archive_reader(self) -> None:
        content = archive_of_empty_members(3)

        with pytest.raises(InvalidEbookError, match="File is not a zip file"):
            read_publication(content[: content.rfind(EOCD_SIGNATURE)])

    def test_a_trailer_cut_off_mid_record_is_refused_rather_than_crashing(self) -> None:
        content = archive_of_empty_members(3)

        with pytest.raises(InvalidEbookError):
            read_publication(content[: content.rfind(EOCD_SIGNATURE) + 8])

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


class TestTheMetadataReadsAsKOReaderReadsIt:
    """The fields a book's KOReader identity is computed from."""

    def epub(self, extra_metadata: str = "", title: str | None = "Hand Built") -> bytes:
        return build_epub(
            CHAPTER_ITEM,
            CHAPTER_SPINE,
            files=("chapter1.xhtml",),
            extra_metadata=extra_metadata,
            title=title,
        )

    def test_every_creator_is_read_trimmed_in_document_order_and_blank_ones_dropped(
        self,
    ) -> None:
        content = self.epub(
            "<dc:creator> Author One </dc:creator><dc:creator> </dc:creator>"
            "<dc:creator>Author Two</dc:creator>"
        )

        metadata = EpubParserService().extract_metadata(content)

        assert metadata == EpubMetadata(
            title="Hand Built", authors=("Author One", "Author Two"), language="en"
        )

    def test_a_book_with_no_creators_has_no_authors(self) -> None:
        assert EpubParserService().extract_metadata(self.epub()).authors == ()

    def test_a_book_with_no_title_has_none(self) -> None:
        assert EpubParserService().extract_metadata(self.epub(title=None)).title is None

    def test_bytes_that_are_not_an_archive_are_not_a_readable_epub(self) -> None:
        with pytest.raises(InvalidEbookError):
            read_epub_metadata(b"not a zip")


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

    def test_a_spine_naming_items_the_manifest_does_not_hold_publishes_the_rest(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        content = build_epub(
            CHAPTER_ITEM,
            f'<itemref idref="ghost"/>{CHAPTER_SPINE}<itemref idref="phantom"/>',
            files=("chapter1.xhtml",),
        )

        with caplog.at_level(logging.WARNING):
            publication = read_publication(content)

        assert hrefs(publication.reading_order) == ["chapter1.xhtml"]
        assert "Dropped 2 spine items" in caplog.text

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


class TestAReadingOrderItemCarriesTheLayoutThePublicationStates:
    """``rendition:layout``, said for the whole publication or per spine item, in Readium's terms.

    A layout nobody states is left unstated rather than defaulted, so a reader
    applies its own; a spine item's own property beats the publication's.
    """

    SPINE = '<itemref idref="ch1"/><itemref idref="ch2"/>'

    def test_a_fixed_layout_book_publishes_the_layout_each_of_its_pages_ends_up_with(self) -> None:
        publication = EpubParserService().parse_publication(FIXED_LAYOUT_EPUB.read_bytes())

        assert publication.metadata.title == "The Fixed Fixture"
        assert hrefs(publication.reading_order) == ["page1.xhtml", "page2.xhtml"]
        assert layouts(publication.reading_order) == [
            PublicationLayout.FIXED,
            PublicationLayout.REFLOWABLE,
        ]
        assert hrefs(publication.resources) == ["nav.xhtml"]
        assert publication.resources[0].layout is None

    def test_an_itemref_overrides_a_reflowable_publication_the_same_way(self) -> None:
        content = self._two_page_epub(
            '<itemref idref="ch1"/>'
            '<itemref idref="ch2" properties="rendition:layout-pre-paginated"/>',
            # The layout metadata is not the publication's only metadata, and
            # says nothing by sitting first.
            extra_metadata='<meta property="dcterms:modified">2024-01-01T00:00:00Z</meta>'
            '<meta property="rendition:layout">reflowable</meta>',
        )

        assert layouts(read_publication(content).reading_order) == [
            PublicationLayout.REFLOWABLE,
            PublicationLayout.FIXED,
        ]

    def test_a_publication_stating_no_layout_leaves_every_item_without_one(self) -> None:
        content = self._two_page_epub(self.SPINE)

        assert layouts(read_publication(content).reading_order) == [None, None]

    def test_a_layout_nobody_recognises_is_no_layout_rather_than_a_guess(self) -> None:
        content = self._two_page_epub(
            self.SPINE,
            extra_metadata='<meta property="rendition:layout">paginated</meta>',
        )

        assert layouts(read_publication(content).reading_order) == [None, None]

    def test_a_layout_value_written_around_whitespace_is_still_read(self) -> None:
        content = self._two_page_epub(
            self.SPINE,
            extra_metadata='<meta property="rendition:layout">\n  pre-paginated\n</meta>',
        )

        assert layouts(read_publication(content).reading_order) == [
            PublicationLayout.FIXED,
            PublicationLayout.FIXED,
        ]

    def test_a_layout_refining_one_chapter_is_not_the_whole_publication_s(self) -> None:
        # A refining meta describes the resource it names; read as the
        # publication's it would flip every page of a reflowable book.
        content = self._two_page_epub(
            self.SPINE,
            extra_metadata=(
                '<meta refines="#ch1" property="rendition:layout">pre-paginated</meta>'
                '<meta property="rendition:layout">reflowable</meta>'
            ),
        )

        assert layouts(read_publication(content).reading_order) == [
            PublicationLayout.REFLOWABLE,
            PublicationLayout.REFLOWABLE,
        ]

    def test_a_layout_property_is_found_among_the_others_an_itemref_carries(self) -> None:
        content = self._two_page_epub(
            '<itemref idref="ch1" properties="page-spread-left'
            ' rendition:layout-pre-paginated rendition:align-x-center"/>'
            '<itemref idref="ch2" properties="page-spread-right"/>'
        )

        assert layouts(read_publication(content).reading_order) == [PublicationLayout.FIXED, None]

    @staticmethod
    def _two_page_epub(spine: str, extra_metadata: str = "") -> bytes:
        return build_epub(
            f'{CHAPTER_ITEM}<item id="ch2" href="chapter2.xhtml"'
            ' media-type="application/xhtml+xml"/>',
            spine,
            files=("chapter1.xhtml", "chapter2.xhtml"),
            extra_metadata=extra_metadata,
        )


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
