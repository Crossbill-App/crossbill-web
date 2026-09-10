"""Tests for the stored form of a parsed publication.

The keys asserted here are the on-disk contract for every ``book_publications``
row already written: renaming one silently invalidates them, so the shape is
pinned as well as round-tripped.
"""

import json
from pathlib import Path

import pytest

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationLayout,
    PublicationMetadata,
    PublicationResource,
    TocEntry,
)
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.mappers.publication_json import (
    publication_from_json,
    publication_to_json,
)

FIXTURES = Path(__file__).parents[3] / "fixtures"
FIXTURE_NAMES = ["minimal", "nested_toc", "fixed_layout"]


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


class TestRoundTrip:
    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_fixture_survives_a_round_trip_through_stored_json(self, name: str) -> None:
        publication = parse_fixture(name)

        stored = json.loads(json.dumps(publication_to_json(publication)))

        assert publication_from_json(stored, publication.content_hash) == publication

    def test_hand_built_publication_survives_a_round_trip_through_stored_json(self) -> None:
        stored = json.loads(json.dumps(publication_to_json(HAND_BUILT)))

        assert publication_from_json(stored, HAND_BUILT.content_hash) == HAND_BUILT

    def test_content_hash_comes_from_the_column_and_not_the_payload(self) -> None:
        payload = publication_to_json(HAND_BUILT)

        assert "content_hash" not in payload
        assert publication_from_json(payload, "f" * 64).content_hash == "f" * 64


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

    def test_nesting_is_written_as_nested_children(self) -> None:
        payload = publication_to_json(parse_fixture("nested_toc"))

        assert [child["title"] for child in payload["toc"][0]["children"]] == [
            "Chapter One",
            "Luku Ääni",
        ]

    def test_top_level_keys(self) -> None:
        payload = publication_to_json(HAND_BUILT)

        assert set(payload) == {"metadata", "reading_order", "resources", "toc"}
