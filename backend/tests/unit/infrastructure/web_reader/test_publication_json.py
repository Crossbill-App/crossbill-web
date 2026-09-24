"""Tests for the stored form of a parsed publication.

The keys asserted here are the on-disk contract for every ``book_publications``
row already written: renaming one silently invalidates them, so the shape is
pinned.
"""

from pathlib import Path

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationLayout,
    PublicationMetadata,
    PublicationResource,
    TocEntry,
)
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.mappers.publication_json import publication_to_json

FIXTURES = Path(__file__).parents[3] / "fixtures"


def parse_fixture(name: str) -> ParsedPublication:
    return read_publication((FIXTURES / f"{name}.epub").read_bytes())


HAND_BUILT = ParsedPublication(
    metadata=PublicationMetadata(title=None, author=None, language=None, identifier=None),
    reading_order=(
        PublicationResource(
            href="EPUB/page%201.xhtml",
            media_type="application/xhtml+xml",
            size=1024,
            layout=PublicationLayout.REFLOWABLE,
        ),
        PublicationResource(
            href="EPUB/page2.xhtml", media_type="application/xhtml+xml", size=2048, layout=None
        ),
    ),
    resources=(
        PublicationResource(href="EPUB/style.css", media_type="text/css", size=12, layout=None),
    ),
    toc=(
        TocEntry(
            title="Part",
            href=None,
            children=(
                TocEntry(
                    title="Chapter",
                    href="EPUB/page%201.xhtml",
                    children=(TocEntry(title="Section", href="EPUB/page2.xhtml#s1", children=()),),
                ),
            ),
        ),
    ),
    content_hash="0" * 64,
)


class TestPayloadShape:
    def test_reading_order_item_keys_and_layout_string(self) -> None:
        payload = publication_to_json(parse_fixture("fixed_layout"))

        assert payload["reading_order"][0] == {
            "href": "page1.xhtml",
            "media_type": "application/xhtml+xml",
            "size": 164,
            "layout": "fixed",
        }

    def test_a_resource_stating_no_layout_carries_no_layout_key(self) -> None:
        payload = publication_to_json(parse_fixture("minimal"))

        assert payload["reading_order"][0] == {
            "href": "OEBPS/chapter1.xhtml",
            "media_type": "application/xhtml+xml",
            "size": 447,
        }

    def test_metadata_and_toc_keys(self) -> None:
        payload = publication_to_json(parse_fixture("minimal"))

        assert payload["metadata"] == {
            "title": "The Lantern Fixture",
            "author": None,
            "language": "en",
            "identifier": "urn:uuid:8f1a0c2e-0000-4000-8000-000000000001",
        }
        assert payload["toc"][0] == {
            "title": "Chapter One",
            "href": "OEBPS/chapter1.xhtml",
            "children": [],
        }

    def test_top_level_keys(self) -> None:
        payload = publication_to_json(HAND_BUILT)

        assert set(payload) == {"metadata", "reading_order", "resources", "toc"}
