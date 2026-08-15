"""Tests for EpubParserService cover extraction and TOC parsing."""

from pathlib import Path

import pytest
from ebooklib import epub

from src.infrastructure.library.services.epub_parser_service import EpubParserService

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
