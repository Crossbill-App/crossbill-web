"""Tests for EpubParserService cover extraction, TOC parsing and archive limits."""

import io
import struct
import tracemalloc
import zipfile
from pathlib import Path

import pytest
from ebooklib import epub

from src.application.web_reader.publications import ParsedPublication, TocEntry
from src.infrastructure.library.services.epub_parser_service import (
    EpubParserService,
    _declared_entry_count,  # pyright: ignore[reportPrivateUsage]
)
from tests.test_readium_manifest import build_epub

FAKE_IMAGE = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR fake image bytes"


def _write_epub(book: epub.EpubBook, path: Path, filename: str) -> Path:
    """Give the book the minimal chapter and navigation it needs, then write it out."""
    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap01.xhtml", lang="en")
    chapter.content = b"<html><body><p>Hello</p></body></html>"
    book.add_item(chapter)
    book.spine = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub_path = path / filename
    epub.write_epub(str(epub_path), book)
    return epub_path


def _create_epub_with_cover_meta(path: Path) -> Path:
    """Create an EPUB where cover is declared via <meta name="cover" content="cover-img"/>
    but ebooklib's get_metadata("OPF", "cover") doesn't return it.

    This simulates the case where ebooklib stores the metadata under
    ("OPF", "meta") instead of ("OPF", "cover") due to namespace handling.
    """
    book = epub.EpubBook()
    book.set_identifier("test-cover-meta")
    book.set_title("Test Cover Meta")
    book.set_language("en")

    # Add a cover image to the manifest
    cover = epub.EpubImage()
    cover.id = "cover-img"
    cover.file_name = "Images/cover.jpg"
    cover.media_type = "image/jpeg"
    cover.content = FAKE_IMAGE
    book.add_item(cover)

    # Add the OPF meta tag linking to the cover image
    # This is the standard EPUB 2 way: <meta name="cover" content="cover-img"/>
    book.add_metadata("OPF", "meta", None, {"name": "cover", "content": "cover-img"})

    return _write_epub(book, path, "cover_meta.epub")


def _create_epub_without_cover(path: Path) -> Path:
    """Create an EPUB with no cover image at all."""
    book = epub.EpubBook()
    book.set_identifier("test-no-cover")
    book.set_title("No Cover")
    book.set_language("en")

    return _write_epub(book, path, "no_cover.epub")


def _create_epub_with_repeated_toc_titles(path: Path) -> Path:
    """Create an EPUB whose nested TOC repeats titles at two levels.

    Shape (mirrors a real book that produced duplicate chapter rows)::

        Osa I
          Luku
            Yhteenveto
            Itsetuntemus
        Osa II
          Luku
            Yhteenveto
    """
    book = epub.EpubBook()
    book.set_identifier("test-repeated-toc")
    book.set_title("Repeated TOC")
    book.set_language("fi")

    files = ["osa1", "luku1", "yhteenveto1", "itsetuntemus", "osa2", "luku2", "yhteenveto2"]
    documents = []
    for name in files:
        document = epub.EpubHtml(title=name, file_name=f"{name}.xhtml", lang="fi")
        document.content = f"<html><body><p>{name}</p></body></html>".encode()
        book.add_item(document)
        documents.append(document)

    book.spine = documents
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.toc = [
        (
            epub.Section("Osa I", href="osa1.xhtml"),
            (
                (
                    epub.Section("Luku", href="luku1.xhtml"),
                    (
                        epub.Link("yhteenveto1.xhtml", "Yhteenveto", "y1"),
                        epub.Link("itsetuntemus.xhtml", "Itsetuntemus", "i1"),
                    ),
                ),
            ),
        ),
        (
            epub.Section("Osa II", href="osa2.xhtml"),
            (
                (
                    epub.Section("Luku", href="luku2.xhtml"),
                    (epub.Link("yhteenveto2.xhtml", "Yhteenveto", "y2"),),
                ),
            ),
        ),
    ]

    epub_path = path / "repeated_toc.epub"
    epub.write_epub(str(epub_path), book)
    return epub_path


@pytest.fixture
def service() -> EpubParserService:
    return EpubParserService()


class TestParseTocHierarchy:
    """Test that parse_toc flattens a nested TOC with unambiguous parent links."""

    def test_repeated_titles_get_distinct_parent_indexes(
        self, service: EpubParserService, tmp_path: Path
    ) -> None:
        epub_path = _create_epub_with_repeated_toc_titles(tmp_path)

        chapters = service.parse_toc(epub_path.read_bytes())

        assert [ch.name for ch in chapters] == [
            "Osa I",
            "Luku",
            "Yhteenveto",
            "Itsetuntemus",
            "Osa II",
            "Luku",
            "Yhteenveto",
        ]
        # Chapter numbers are sequential and unique across the whole TOC
        assert [ch.chapter_number for ch in chapters] == [1, 2, 3, 4, 5, 6, 7]
        # Each entry points at its parent's position, so the two "Luku" sections
        # and the two "Yhteenveto" leaves stay distinguishable despite the names
        assert [ch.parent_index for ch in chapters] == [None, 0, 1, 1, None, 4, 5]
        # parent_name is kept for callers without indexes
        assert [ch.parent_name for ch in chapters] == [
            None,
            "Osa I",
            "Luku",
            "Luku",
            None,
            "Osa II",
            "Luku",
        ]


class TestExtractCoverFromOPFMeta:
    """Test Strategy 3: extract cover by scanning OPF 'meta' entries."""

    def test_extracts_cover_from_opf_meta_entries(
        self, service: EpubParserService, tmp_path: Path
    ) -> None:
        epub_path = _create_epub_with_cover_meta(tmp_path)

        # Verify that ebooklib's get_metadata("OPF", "cover") misses it
        book = epub.read_epub(str(epub_path))
        assert book.get_metadata("OPF", "cover") == []

        # But our service should still find the cover
        result = service.extract_cover(epub_path.read_bytes())
        assert result is not None
        assert result == FAKE_IMAGE

    def test_returns_none_when_no_cover(self, service: EpubParserService, tmp_path: Path) -> None:
        epub_path = _create_epub_without_cover(tmp_path)
        result = service.extract_cover(epub_path.read_bytes())
        assert result is None


class TestParsePublicationCost:
    """What resolving a publication's structure *costs*, which no manifest can show.

    Every readium request parses the stored EPUB, so the parse decides what one
    request may be made to allocate. The bytes it must read are the container,
    the package document and the navigation document -- a few kilobytes of
    structure -- and nothing about a manifest entry requires reading the file it
    names. Reading them all is a per-request tax the size of the whole book on
    an honest one, and unbounded amplification on a crafted one: this archive is
    130 KB and its members inflate to 128 MiB (#773).
    """

    # Large enough that inflating the publication cannot hide inside the noise
    # of a parse, small enough to build in a test.
    BOMB_SIZE = 128 * 1024 * 1024

    # A parse reads three small documents and builds a dataclass per manifest
    # item, so its peak has nothing to do with how much content the archive
    # holds. Loose enough not to fail on an interpreter's own allocations,
    # tight enough that reading one member of any real book would break it.
    PEAK_LIMIT = 8 * 1024 * 1024

    @staticmethod
    def _high_ratio_epub(size: int) -> bytes:
        """A publication whose members really do inflate to ``size``, honestly declared.

        Nothing here is a lie the size guards could catch: the central directory
        states the real uncompressed length, which is well under the limit the
        parser admits. The archive is simply very compressible, as a book of
        repeated markup is.
        """
        return build_epub(
            manifest_items=(
                '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="big" href="big.css" media-type="text/css"/>'
            ),
            spine='<itemref idref="c1"/>',
            nav_links='<li><a href="c1.xhtml">One</a></li>',
            files=("c1.xhtml", "big.css"),
            bodies={"big.css": b"A" * size},
            compression=zipfile.ZIP_DEFLATED,
        )

    @staticmethod
    def _peak_bytes_parsing(
        service: EpubParserService, content: bytes
    ) -> tuple[ParsedPublication, int]:
        """Parse a publication and report what the parse peaked at."""
        tracemalloc.start()
        try:
            publication = service.parse_publication(content)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        return publication, peak

    def test_reads_the_structure_without_inflating_the_content(
        self, service: EpubParserService
    ) -> None:
        """Should cost what the package and navigation documents weigh, not the book."""
        content = self._high_ratio_epub(self.BOMB_SIZE)
        assert len(content) < 256 * 1024, "the archive itself should be small"

        publication, peak = self._peak_bytes_parsing(service, content)

        # The publication is still resolved in full: the point is the cost, not
        # a narrower answer.
        assert [item.href for item in publication.reading_order] == ["c1.xhtml"]
        assert [item.href for item in publication.resources] == ["nav.xhtml", "big.css"]
        assert [entry.title for entry in publication.toc] == ["One"]
        assert peak < self.PEAK_LIMIT, f"inflated the publication: {peak / 1024**2:.0f} MiB"


def hand_built_epub(package: str, members: dict[str, str], opf_path: str = "content.opf") -> bytes:
    """An EPUB assembled member by member, for shapes ``build_epub`` cannot take.

    ``build_epub`` writes an EPUB 3 with a navigation document, which is the
    shape nearly every assertion wants. These are the ones it is not: a book
    navigated by an NCX, or one whose navigation is broken.
    """
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            f'<rootfile full-path="{opf_path}" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        archive.writestr(opf_path, package)
        for name, body in members.items():
            archive.writestr(name, body)
    return out.getvalue()


def package_document(metadata: str, manifest: str, spine: str, unique_id: str = "i") -> str:
    """A package document, with the three parts a test varies written out."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        f'unique-identifier="{unique_id}">'
        f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{metadata}</metadata>'
        f"<manifest>{manifest}</manifest>{spine}</package>"
    )


DC_METADATA = (
    '<dc:identifier id="i">urn:uuid:hand-built</dc:identifier>'
    "<dc:title>Hand Built</dc:title><dc:language>en</dc:language>"
)
CHAPTER = '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Hi there.</p></body></html>'
NCX = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><navMap>'
    '<navPoint id="p1"><navLabel><text>Part One</text></navLabel>'
    '<content src="c1.xhtml"/>'
    '<navPoint id="p1a"><navLabel><text>Chapter One</text></navLabel>'
    '<content src="c1.xhtml#sec1"/></navPoint>'
    "</navPoint>"
    '<navPoint id="p2"><navLabel><text>Appendix</text></navLabel>'
    '<content src="c2.xhtml"/></navPoint>'
    "</navMap></ncx>"
)
NAV_DOCUMENT = (
    '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
    '<body><nav epub:type="toc"><ol><li><a href="c1.xhtml">From the nav document</a></li>'
    "</ol></nav></body></html>"
)


class TestPublicationNavigation:
    """Where a publication's table of contents comes from.

    EPUB 3 states it in a navigation document and EPUB 2 in an NCX, and a
    library's catalogue holds both. Neither is reachable through the manifest
    fixtures, which are all EPUB 3, and both are ordinary tree-walking over a
    document -- the case the unit tier is for.
    """

    def test_reads_a_nested_table_of_contents_from_an_ncx(self, service: EpubParserService) -> None:
        """Should navigate an EPUB 2, which has no navigation document at all."""
        content = hand_built_epub(
            package_document(
                DC_METADATA,
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="c2" href="c2.xhtml" media-type="application/xhtml+xml"/>',
                '<spine toc="ncx"><itemref idref="c1"/><itemref idref="c2"/></spine>',
            ),
            {"toc.ncx": NCX, "c1.xhtml": CHAPTER, "c2.xhtml": CHAPTER},
        )

        publication = service.parse_publication(content)

        assert publication.toc == (
            TocEntry(
                title="Part One",
                href="c1.xhtml",
                children=(TocEntry(title="Chapter One", href="c1.xhtml#sec1"),),
            ),
            TocEntry(title="Appendix", href="c2.xhtml"),
        )

    def test_prefers_the_navigation_document_to_the_ncx(self, service: EpubParserService) -> None:
        """Should read the navigation of the version the publication declares.

        A publication carrying both is an EPUB 3 keeping an NCX for older
        readers, and the two disagree often enough to matter: the NCX is the
        copy that stops being maintained.
        """
        content = hand_built_epub(
            package_document(
                DC_METADATA,
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
                '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                'properties="nav"/>'
                '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>',
                '<spine toc="ncx"><itemref idref="c1"/></spine>',
            ),
            {"toc.ncx": NCX, "nav.xhtml": NAV_DOCUMENT, "c1.xhtml": CHAPTER},
        )

        publication = service.parse_publication(content)

        assert [entry.title for entry in publication.toc] == ["From the nav document"]

    def test_a_publication_whose_navigation_is_unreadable_still_opens(
        self, service: EpubParserService
    ) -> None:
        """Should lose the table of contents rather than the book.

        The reading order is what a reader opens; a navigation document that is
        missing, malformed or states no ``toc`` costs the lines a reader jumps
        by, and nothing else.
        """
        content = hand_built_epub(
            package_document(
                DC_METADATA,
                '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                'properties="nav"/>'
                '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>',
                '<spine><itemref idref="c1"/></spine>',
            ),
            {"c1.xhtml": CHAPTER},
        )

        publication = service.parse_publication(content)

        assert publication.toc == ()
        assert [item.href for item in publication.reading_order] == ["c1.xhtml"]


class TestPublicationIdentifier:
    """Which ``dc:identifier`` a manifest publishes, and that it is the book's own.

    A reader keys its stored state on the identifier, so one that moved between
    two requests for the same book would scatter that state across identities
    that never existed.
    """

    @staticmethod
    def _epub_identified_by(metadata: str, unique_id: str = "i") -> bytes:
        return hand_built_epub(
            package_document(
                metadata,
                '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>',
                '<spine><itemref idref="c1"/></spine>',
                unique_id=unique_id,
            ),
            {"c1.xhtml": CHAPTER},
        )

    def test_publishes_the_identifier_the_package_marks_unique(
        self, service: EpubParserService
    ) -> None:
        """Should pick the named one out of several, not merely the first."""
        content = self._epub_identified_by(
            '<dc:identifier id="isbn">urn:isbn:9780000000001</dc:identifier>'
            '<dc:identifier id="uuid">urn:uuid:0000</dc:identifier>',
            unique_id="uuid",
        )

        assert service.parse_publication(content).metadata.identifier == "urn:uuid:0000"

    def test_publishes_an_identifier_the_package_marks_as_nothing(
        self, service: EpubParserService
    ) -> None:
        """Should still name the book when no identifier carries the marked id.

        The identifier a broken package states is worth publishing; an invented
        one is not, and a fresh one per request least of all.
        """
        content = self._epub_identified_by("<dc:identifier>urn:uuid:unmarked</dc:identifier>")

        first = service.parse_publication(content).metadata.identifier
        second = service.parse_publication(content).metadata.identifier

        assert first == "urn:uuid:unmarked"
        assert second == first


class TestDeclaredEntryCount:
    """Reading an archive's entry count out of its trailer, before opening it.

    A unit test rather than an endpoint one: this is zip-format parsing with a
    branch the manifest tests cannot reach, because the ZIP64 arm needs an
    archive with more than 65,535 members and nothing about it involves HTTP.
    """

    @staticmethod
    def _archive(entries: int, comment: bytes = b"") -> bytes:
        """Build a real zip of empty members, so the trailer is Python's, not ours."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
            for index in range(entries):
                archive.writestr(str(index), b"")
            archive.comment = comment
        return buffer.getvalue()

    @pytest.mark.parametrize("entries", [0, 1, 7, 300])
    def test_reads_the_count_from_the_end_of_central_directory(self, entries: int) -> None:
        assert _declared_entry_count(self._archive(entries)) == entries

    def test_follows_the_zip64_record_past_the_sixteen_bit_limit(self) -> None:
        """Above 65,535 the count field holds 0xFFFF and the real total is in ZIP64.

        Taking the sentinel at face value would read 65,535 for an archive of
        any size, which is exactly the archive the limit exists to stop.
        """
        archive = self._archive(65_536)

        eocd = archive.rfind(b"PK\x05\x06")
        assert struct.unpack_from("<H", archive, eocd + 10)[0] == 0xFFFF, "no sentinel to follow"
        assert _declared_entry_count(archive) == 65_536

    def test_finds_the_record_behind_a_trailing_comment(self) -> None:
        """The EOCD is not at the end of file when the archive carries a comment."""
        assert _declared_entry_count(self._archive(4, comment=b"x" * 3000)) == 4

    @pytest.mark.parametrize(
        ("label", "content"),
        [
            ("empty", b""),
            ("not a zip", b"nothing like an archive"),
            ("truncated trailer", b"PK\x05\x06short"),
        ],
    )
    def test_reports_nothing_for_an_archive_it_cannot_read(
        self, label: str, content: bytes
    ) -> None:
        """Should decline to answer rather than raise; ZipFile will refuse it next."""
        assert _declared_entry_count(content) is None, label
