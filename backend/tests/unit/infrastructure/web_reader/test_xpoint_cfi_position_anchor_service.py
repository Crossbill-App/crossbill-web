"""Tests for the position-anchor adapter.

The adapter is the highest seam that exists -- nothing derives an anchor yet
(R4.2) -- and it needs no mocking to exercise: EPUB bytes in, Locators out, with
the real parse and the real locator maths in between.

The fixture book is ``tests/fixtures/minimal.epub``: two chapters, ``<em>``
nested inside a paragraph, and one sentence repeated in two paragraphs of
chapter one, which is what makes ``text.before`` / ``text.after`` load-bearing.
"""

import io
import struct
import zipfile

import pytest
import xpoint_cfi

from src.application.web_reader.anchors import AnchorResolutionError, Locator, LocatorLocations
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.domain.common.value_objects.xpoint import XPoint, XPointRange
from src.infrastructure.web_reader.services.xpoint_cfi_position_anchor_service import (
    XPointCfiPositionAnchorService,
)
from tests.readium_helpers import fixture_bytes

# The second of the two identical paragraphs in chapter one. A locator built
# from it must name p[3], not p[1].
REPEATED_SENTENCE = XPointRange.parse(
    "/body/DocFragment[1]/body/div/p[3]/text().0",
    "/body/DocFragment[1]/body/div/p[3]/text().32",
)
REPEATED_SENTENCE_TEXT = "The lantern went out at midnight"

NESTED_EMPHASIS = XPointRange.parse(
    "/body/DocFragment[1]/body/div/p[2]/em/text().0",
    "/body/DocFragment[1]/body/div/p[2]/em/text().17",
)

MISSING_SPINE_ITEM = XPointRange.parse(
    "/body/DocFragment[9]/body/div/p[1]/text().0",
    "/body/DocFragment[9]/body/div/p[1]/text().5",
)

CHAPTER_ONE_POINT = XPoint.parse("/body/DocFragment[1]/body/div/p[1]/text().4")
CHAPTER_TWO_POINT = XPoint.parse("/body/DocFragment[2]/body/div/p[1]/text().8")

# A caret at offset 0 serializes without its ``/text().0``, which is the ordinary
# shape of a KOReader caret and the one an element-boundary range would mistake.
PARAGRAPH_START = XPoint.parse("/body/DocFragment[2]/body/div/p[1]/text().0")

# crengine before DOM version 20200223 wrapped runs in boxing elements, and
# devices still hold highlights written against that DOM.
BOXED_POINT = XPoint.parse("/body/DocFragment[1]/body/autoBoxing[1]/p/text().0")


def with_corrupt_stream(epub: bytes, member: str) -> bytes:
    """Return the archive with one member's compressed bytes flipped.

    The zip index stays intact, so the member fails when it is decompressed
    rather than when the archive is opened -- which is where a real EPUB with a
    damaged stream fails too.
    """
    entry = zipfile.ZipFile(io.BytesIO(epub)).getinfo(member)
    data = bytearray(epub)
    header = entry.header_offset
    name_length, extra_length = struct.unpack("<HH", data[header + 26 : header + 30])
    start = header + 30 + name_length + extra_length
    for index in range(start, start + entry.compress_size):
        data[index] ^= 0xFF
    return bytes(data)


@pytest.fixture
def epub() -> bytes:
    return fixture_bytes("minimal")


@pytest.fixture
def anchors() -> PositionAnchorServiceProtocol:
    return XPointCfiPositionAnchorService()


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    """Records the bytes handed to every EPUB parse the library performs."""
    parsed: list[bytes] = []
    real = xpoint_cfi.EpubMap.from_bytes

    def counting(data: bytes) -> xpoint_cfi.EpubMap:
        parsed.append(data)
        return real(data)

    monkeypatch.setattr(xpoint_cfi.EpubMap, "from_bytes", counting)
    return parsed


class TestXPointToLocator:
    async def test_a_range_becomes_a_locator_quoting_the_highlighted_text(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoint_ranges(epub, {7: REPEATED_SENTENCE})

        locator = locators[7]
        assert locator is not None
        assert locator.href == "OEBPS/chapter1.xhtml"
        assert locator.type == "application/xhtml+xml"
        assert locator.text.highlight == REPEATED_SENTENCE_TEXT
        # #intro's children are h1, p, p, p, p, so the second of the two
        # identical paragraphs is nth-child(4).
        assert locator.locations.css_selector == "#intro > p:nth-child(4)"
        assert locator.text.before is not None
        assert locator.text.before.rstrip().endswith("twice, and meant it both times.")

    async def test_a_range_inside_inline_markup_selects_that_element(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoint_ranges(epub, {7: NESTED_EMPHASIS})

        locator = locators[7]
        assert locator is not None
        assert locator.text.highlight == "the same sentence"
        assert locator.locations.css_selector == "#intro > p:nth-child(3) > em:nth-child(1)"

    async def test_a_single_position_is_a_caret_with_context_but_no_quote(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoints(epub, {"end": CHAPTER_TWO_POINT})

        locator = locators["end"]
        assert locator is not None
        assert locator.href == "OEBPS/chapter2.xhtml"
        assert locator.text.highlight == ""
        assert locator.text.before is not None
        assert locator.text.before.endswith("Morning ")
        assert locator.text.after is not None
        assert locator.text.after.startswith("arrived without ceremony.")
        assert locator.locations.progression is not None
        assert 0.0 < locator.locations.progression < 1.0

    async def test_a_position_at_the_start_of_a_paragraph_is_a_caret_too(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoints(epub, {"start": PARAGRAPH_START})

        locator = locators["start"]
        assert locator is not None
        assert locator.text.highlight == ""
        assert locator.text.after is not None
        assert locator.text.after.startswith("Morning arrived without ceremony.")

    async def test_both_ends_of_a_session_convert_under_one_set_of_keys(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        points = {(42, "start"): CHAPTER_ONE_POINT}
        points[(42, "end")] = CHAPTER_TWO_POINT

        locators = await anchors.locators_for_xpoints(epub, points)

        assert locators[(42, "start")] is not None
        assert locators[(42, "start")].href == "OEBPS/chapter1.xhtml"  # pyright: ignore[reportOptionalMemberAccess]
        assert locators[(42, "end")] is not None
        assert locators[(42, "end")].href == "OEBPS/chapter2.xhtml"  # pyright: ignore[reportOptionalMemberAccess]


class TestReadiumJsonShape:
    async def test_a_derived_locator_serializes_with_camel_case_keys(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoint_ranges(epub, {7: REPEATED_SENTENCE})
        locator = locators[7]
        assert locator is not None

        payload = locator.to_dict()

        assert payload["href"] == "OEBPS/chapter1.xhtml"
        assert payload["locations"] == {
            "progression": locator.locations.progression,
            "cssSelector": "#intro > p:nth-child(4)",
        }
        assert payload["text"] == {  # pyright: ignore[reportUnknownMemberType]
            "before": locator.text.before,
            "highlight": REPEATED_SENTENCE_TEXT,
            "after": locator.text.after,
        }

    async def test_a_caret_serializes_its_empty_highlight(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoints(epub, {7: CHAPTER_TWO_POINT})
        locator = locators[7]
        assert locator is not None

        assert locator.to_dict()["text"] == {  # pyright: ignore[reportUnknownMemberType]
            "before": locator.text.before,
            "highlight": "",
            "after": locator.text.after,
        }

    def test_unset_fields_are_absent_rather_than_null(self) -> None:
        bare = Locator(href="OEBPS/chapter1.xhtml", type="application/xhtml+xml")

        assert bare.to_dict() == {"href": "OEBPS/chapter1.xhtml", "type": "application/xhtml+xml"}

    def test_a_progression_at_the_start_of_a_resource_is_serialized(self) -> None:
        assert LocatorLocations(progression=0.0).to_dict() == {"progression": 0.0}


class TestFailure:
    async def test_a_range_naming_a_missing_spine_item_is_none(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoint_ranges(
            epub, {1: REPEATED_SENTENCE, 2: MISSING_SPINE_ITEM, 3: NESTED_EMPHASIS}
        )

        assert locators[2] is None
        assert locators[1] is not None
        assert locators[3] is not None

    async def test_a_point_that_does_not_resolve_is_none(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        nowhere = XPoint.parse("/body/DocFragment[1]/body/div/p[99]/text().0")

        locators = await anchors.locators_for_xpoints(epub, {1: nowhere, 2: CHAPTER_TWO_POINT})

        assert locators[1] is None
        assert locators[2] is not None

    async def test_an_unparseable_xpointer_is_none_while_the_batch_resolves(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoints(epub, {1: BOXED_POINT, 2: CHAPTER_TWO_POINT})

        assert locators[1] is None
        assert locators[2] is not None

    async def test_bytes_that_are_not_an_epub_fail_the_whole_batch(
        self, anchors: PositionAnchorServiceProtocol
    ) -> None:
        with pytest.raises(AnchorResolutionError, match="Cannot read EPUB"):
            await anchors.locators_for_xpoint_ranges(
                b"not a zip archive at all", {1: REPEATED_SENTENCE}
            )

    async def test_an_archive_whose_container_is_damaged_fails_the_whole_batch(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        broken = with_corrupt_stream(epub, "META-INF/container.xml")

        with pytest.raises(AnchorResolutionError, match="Cannot read EPUB"):
            await anchors.locators_for_xpoint_ranges(broken, {1: REPEATED_SENTENCE})

    async def test_a_damaged_document_fails_only_the_positions_inside_it(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        broken = with_corrupt_stream(epub, "OEBPS/chapter1.xhtml")

        locators = await anchors.locators_for_xpoints(
            broken, {1: CHAPTER_ONE_POINT, 2: CHAPTER_TWO_POINT}
        )

        assert locators[1] is None
        assert locators[2] is not None

    async def test_an_empty_batch_returns_nothing_without_reading_the_epub(
        self, anchors: PositionAnchorServiceProtocol, parses: list[bytes]
    ) -> None:
        assert await anchors.locators_for_xpoint_ranges(b"not a zip archive at all", {}) == {}
        assert await anchors.locators_for_xpoints(b"not a zip archive at all", {}) == {}
        assert parses == []


class TestOneParsePerBatch:
    async def test_a_batch_of_ranges_parses_the_fixture_once(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes, parses: list[bytes]
    ) -> None:
        await anchors.locators_for_xpoint_ranges(
            epub, {1: REPEATED_SENTENCE, 2: NESTED_EMPHASIS, 3: MISSING_SPINE_ITEM}
        )

        assert parses == [epub]
