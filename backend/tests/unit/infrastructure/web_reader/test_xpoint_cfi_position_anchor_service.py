"""Tests for the position-anchor adapter.

The adapter is the highest seam that exists -- nothing derives an anchor yet
(R4.2) -- and it needs no mocking to exercise: EPUB bytes in, Locators out and
back, with the real parse and the real locator maths in between.

The fixture book is ``tests/fixtures/minimal.epub``: two chapters, ``<em>``
nested inside a paragraph, and one sentence repeated in two paragraphs of
chapter one, which is what makes ``text.before`` / ``text.after`` load-bearing.
"""

import io
import struct
import zipfile

import pytest
import xpoint_cfi

from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorNotFoundError,
    AnchorResolutionError,
    Locator,
    LocatorLocations,
    LocatorText,
)
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

# The text abutting the *second* occurrence on either side, and nowhere abutting
# the first: whichever of the two a Locator carries has to decide the match.
BEFORE_SECOND = "twice, and meant it both times."
AFTER_SECOND = ". Nothing else in the house moved"

UNIQUE_SENTENCE = "Nothing else in the house moved"
MISSPELLED_SENTENCE = "The lantern went out at midnite."

NESTED_EMPHASIS = XPointRange.parse(
    "/body/DocFragment[1]/body/div/p[2]/em/text().0",
    "/body/DocFragment[1]/body/div/p[2]/em/text().17",
)

# Starts in the text before the ``<em>`` and ends in the text after it, so the end
# names the paragraph's *second* text node.
SPANNING_EMPHASIS = XPointRange.parse(
    "/body/DocFragment[1]/body/div/p[2]/text().4",
    "/body/DocFragment[1]/body/div/p[2]/text()[2].6",
)
SPANNING_EMPHASIS_TEXT = "wrote the same sentence twice"

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


def with_replaced_member(epub: bytes, member: str, content: bytes) -> bytes:
    """Return the archive rebuilt with one member's content replaced.

    Unlike ``with_corrupt_stream``, the member decompresses cleanly, so what fails
    is the document rather than the archive around it.
    """
    source = zipfile.ZipFile(io.BytesIO(epub))
    rebuilt = io.BytesIO()
    with zipfile.ZipFile(rebuilt, "w") as target:
        for entry in source.infolist():
            data = content if entry.filename == member else source.read(entry.filename)
            target.writestr(entry, data)
    return rebuilt.getvalue()


def chapter_one_locator(
    before: str | None = None, highlight: str | None = None, after: str | None = None
) -> Locator:
    """A Locator into chapter one carrying only the quote given, as a browser sends one."""
    return Locator(
        href="OEBPS/chapter1.xhtml",
        type="application/xhtml+xml",
        text=LocatorText(before=before, highlight=highlight, after=after),
    )


@pytest.fixture
def epub() -> bytes:
    return fixture_bytes("minimal")


@pytest.fixture
def anchors() -> PositionAnchorServiceProtocol:
    return XPointCfiPositionAnchorService()


@pytest.fixture
async def derived(anchors: PositionAnchorServiceProtocol, epub: bytes) -> Locator:
    """The Locator the forward conversion builds for ``REPEATED_SENTENCE``."""
    locators = await anchors.locators_for_xpoint_ranges(epub, {7: REPEATED_SENTENCE})
    locator = locators[7]
    assert locator is not None
    return locator


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


class TestLocatorToXPoint:
    async def test_a_derived_locator_round_trips_to_the_range_it_came_from(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes, derived: Locator
    ) -> None:
        match = await anchors.xpoint_range_for_locator(epub, derived)

        # The library normalizes a bare ``div`` to ``div[1]``; the position is the same.
        assert match.xpoints.start.doc_fragment_index == 1
        assert match.xpoints.start.xpath == "/body/div[1]/p[3]"
        assert match.xpoints.start.char_offset == 0
        assert match.xpoints.end.char_offset == 32
        assert match.confidence is AnchorConfidence.BOTH_CONTEXTS

    async def test_a_range_ending_past_inline_markup_keeps_the_later_text_nodes_index(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoint_ranges(epub, {7: SPANNING_EMPHASIS})
        spanning = locators[7]
        assert spanning is not None
        assert spanning.text.highlight == SPANNING_EMPHASIS_TEXT

        match = await anchors.xpoint_range_for_locator(epub, spanning)

        assert match.xpoints.start.xpath == "/body/div[1]/p[2]"
        assert match.xpoints.start.text_node_index == 1
        assert match.xpoints.start.char_offset == 4
        assert match.xpoints.end.xpath == "/body/div[1]/p[2]"
        assert match.xpoints.end.text_node_index == 2
        assert match.xpoints.end.char_offset == 6
        assert match.confidence is AnchorConfidence.BOTH_CONTEXTS

    async def test_a_caret_locator_round_trips_to_the_position_it_came_from(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        """A caret has no quote, only the two contexts meeting at it."""
        locators = await anchors.locators_for_xpoints(epub, {7: CHAPTER_TWO_POINT})
        caret = locators[7]
        assert caret is not None

        match = await anchors.xpoint_range_for_locator(epub, caret)

        assert match.xpoints.start == match.xpoints.end
        assert match.xpoints.start.doc_fragment_index == 2
        assert match.xpoints.start.xpath == "/body/div[1]/p[1]"
        assert match.xpoints.start.char_offset == 8
        assert match.confidence is AnchorConfidence.BOTH_CONTEXTS

    async def test_leading_context_decides_which_occurrence_of_the_sentence_wins(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locator = chapter_one_locator(before=BEFORE_SECOND, highlight=REPEATED_SENTENCE_TEXT)

        match = await anchors.xpoint_range_for_locator(epub, locator)

        assert match.xpoints.start.xpath == "/body/div[1]/p[3]"
        assert match.confidence is AnchorConfidence.ONE_CONTEXT

    async def test_trailing_context_decides_it_just_as_well(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locator = chapter_one_locator(highlight=REPEATED_SENTENCE_TEXT, after=AFTER_SECOND)

        match = await anchors.xpoint_range_for_locator(epub, locator)

        assert match.xpoints.start.xpath == "/body/div[1]/p[3]"
        assert match.confidence is AnchorConfidence.ONE_CONTEXT

    async def test_the_same_quote_with_no_context_lands_on_the_first_occurrence(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        """What the two context tests above are measured against."""
        locator = chapter_one_locator(highlight=REPEATED_SENTENCE_TEXT)

        match = await anchors.xpoint_range_for_locator(epub, locator)

        assert match.xpoints.start.xpath == "/body/div[1]/p[1]"
        assert match.confidence is AnchorConfidence.AMBIGUOUS

    async def test_the_css_selector_narrows_where_a_contextless_quote_may_land(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        # #intro's children are h1, p, p, p, p, so the second occurrence is nth-child(4).
        scoped = Locator(
            href="OEBPS/chapter1.xhtml",
            type="application/xhtml+xml",
            locations=LocatorLocations(css_selector="#intro > p:nth-child(4)"),
            text=LocatorText(highlight=REPEATED_SENTENCE_TEXT),
        )

        match = await anchors.xpoint_range_for_locator(epub, scoped)

        assert match.xpoints.start.xpath == "/body/div[1]/p[3]"
        assert match.confidence is AnchorConfidence.HIGHLIGHT_ONLY

    async def test_a_weak_match_grades_below_a_strong_one_so_a_caller_can_set_a_floor(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        alone = await anchors.xpoint_range_for_locator(
            epub, chapter_one_locator(highlight=UNIQUE_SENTENCE)
        )
        approximate = await anchors.xpoint_range_for_locator(
            epub, chapter_one_locator(highlight=MISSPELLED_SENTENCE)
        )

        assert approximate.confidence is AnchorConfidence.FUZZY
        assert alone.confidence is AnchorConfidence.HIGHLIGHT_ONLY
        assert approximate.confidence < alone.confidence < AnchorConfidence.ONE_CONTEXT


class TestLocatorToXPointFailure:
    async def test_a_locator_naming_no_resource_of_this_book_raises(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        elsewhere = Locator(
            href="OEBPS/chapter9.xhtml",
            type="application/xhtml+xml",
            text=LocatorText(highlight=REPEATED_SENTENCE_TEXT),
        )

        with pytest.raises(AnchorNotFoundError, match="Cannot place locator"):
            await anchors.xpoint_range_for_locator(epub, elsewhere)

    async def test_a_quote_that_is_nowhere_in_the_book_raises(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        absent = chapter_one_locator(highlight="a phrase this book has never contained anywhere")

        with pytest.raises(AnchorNotFoundError, match="Cannot place locator"):
            await anchors.xpoint_range_for_locator(epub, absent)

    async def test_a_locator_carrying_no_text_at_all_raises(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        """The ordinary shape of a reading position, which #830 anchors instead."""
        bare = Locator(href="OEBPS/chapter1.xhtml", type="application/xhtml+xml")

        with pytest.raises(AnchorNotFoundError, match="carries no text"):
            await anchors.xpoint_range_for_locator(epub, bare)

    async def test_a_locator_whose_text_is_only_whitespace_raises_without_a_parse(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes, parses: list[bytes]
    ) -> None:
        blank = chapter_one_locator(before="\n  ", highlight="   ", after=" ")

        with pytest.raises(AnchorNotFoundError, match="carries no text"):
            await anchors.xpoint_range_for_locator(epub, blank)

        assert parses == []

    async def test_a_caller_catching_the_base_error_catches_a_missing_place_too(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        """#830 catches the base to degrade both failures at once."""
        absent = chapter_one_locator(highlight="a phrase this book has never contained anywhere")

        with pytest.raises(AnchorResolutionError):
            await anchors.xpoint_range_for_locator(epub, absent)

    async def test_bytes_that_are_not_an_epub_raise(
        self, anchors: PositionAnchorServiceProtocol
    ) -> None:
        quote = chapter_one_locator(highlight=REPEATED_SENTENCE_TEXT)

        with pytest.raises(AnchorResolutionError, match="Cannot read EPUB"):
            await anchors.xpoint_range_for_locator(b"not a zip archive at all", quote)

    async def test_a_damaged_document_raises_rather_than_resolving_elsewhere(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        """One locator has no partial success to preserve, unlike a batch."""
        broken = with_corrupt_stream(epub, "OEBPS/chapter1.xhtml")
        quote = chapter_one_locator(highlight=REPEATED_SENTENCE_TEXT)

        with pytest.raises(AnchorResolutionError, match="Cannot read EPUB"):
            await anchors.xpoint_range_for_locator(broken, quote)

    async def test_a_document_that_is_not_xml_is_the_books_failure_not_the_locators(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        """Every locator into it fails together, which is what the base class means."""
        broken = with_replaced_member(epub, "OEBPS/chapter1.xhtml", b"plain text, not markup")
        quote = chapter_one_locator(highlight=REPEATED_SENTENCE_TEXT)

        with pytest.raises(AnchorResolutionError, match="Cannot read EPUB") as raised:
            await anchors.xpoint_range_for_locator(broken, quote)

        assert type(raised.value) is AnchorResolutionError


class TestVerification:
    async def test_a_derived_anchor_verifies_against_the_stored_highlight_text(
        self, anchors: PositionAnchorServiceProtocol, derived: Locator
    ) -> None:
        # Whitespace differs between crengine's exported highlight and the EPUB's DOM.
        assert anchors.verify_locator(derived, "The  lantern went\n out at midnight  ") is True

    def test_a_soft_hyphen_in_the_documents_text_does_not_count_against_a_match(
        self, anchors: PositionAnchorServiceProtocol
    ) -> None:
        # crengine keeps soft hyphens in its DOM text and strips them from its export.
        hyphenated = chapter_one_locator(highlight="The lantern went out at mid\u00adnight")

        assert anchors.verify_locator(hyphenated, REPEATED_SENTENCE_TEXT) is True

    async def test_an_anchor_covering_a_different_passage_is_rejected(
        self, anchors: PositionAnchorServiceProtocol, derived: Locator
    ) -> None:
        """What a replaced EPUB looks like: the anchor resolved, to the wrong text."""
        assert anchors.verify_locator(derived, UNIQUE_SENTENCE) is False

    async def test_a_caret_verifies_only_against_empty_text(
        self, anchors: PositionAnchorServiceProtocol, epub: bytes
    ) -> None:
        locators = await anchors.locators_for_xpoints(epub, {7: CHAPTER_TWO_POINT})
        caret = locators[7]
        assert caret is not None

        assert anchors.verify_locator(caret, "") is True
        assert anchors.verify_locator(caret, "Morning") is False

    def test_a_locator_carrying_no_quote_at_all_verifies_against_empty_text(
        self, anchors: PositionAnchorServiceProtocol
    ) -> None:
        """The reading position #830 hands this: no ``highlight`` key, not an empty one."""
        position = chapter_one_locator(before="Morning ")

        assert anchors.verify_locator(position, "") is True
        assert anchors.verify_locator(position, "Morning") is False
