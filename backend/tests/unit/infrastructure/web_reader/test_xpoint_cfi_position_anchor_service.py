"""Tests for the position-anchor adapter, exercised through its two ports.

The seam is the adapter itself: no endpoint derives an anchor yet (that is M1/M3),
so the port is the highest one that exists. Everything below it -- the EPUB
parse, the locator maths -- is real; only the EPUB store is faked, and only so
the tests can count how often the bytes are fetched.

The fixture book is ``tests/fixtures/minimal.epub``: two chapters, ``<em>``
nested inside a paragraph, and one sentence repeated in two paragraphs of
chapter one, which is what makes ``text.before`` / ``text.after`` load-bearing.
The conftest ``build_test_epub`` helper is too thin for that -- one paragraph,
no repetition, no inline markup.
"""

import io
import zipfile
from pathlib import Path

import pytest

from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorResolutionError,
    Locator,
    LocatorText,
)
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.application.web_reader.protocols.publication_cache import PublicationCacheProtocol
from src.domain.common.value_objects.xpoint import XPoint, XPointRange
from src.infrastructure.web_reader.services.xpoint_cfi_position_anchor_service import (
    PARSED_PUBLICATION_CACHE_SIZE,
    XPointCfiPositionAnchorService,
)

EBOOK_FILE = "minimal.epub"

# The second of the two identical paragraphs in chapter one. A locator built
# from it must come back to p[3], not p[1].
REPEATED_SENTENCE = XPointRange.parse(
    "/body/DocFragment[1]/body/div/p[3]/text().0",
    "/body/DocFragment[1]/body/div/p[3]/text().32",
)
REPEATED_SENTENCE_TEXT = "The lantern went out at midnight"

# The text inside <em>, i.e. a range that starts and ends below an inline element.
NESTED_EMPHASIS = XPointRange.parse(
    "/body/DocFragment[1]/body/div/p[2]/em/text().0",
    "/body/DocFragment[1]/body/div/p[2]/em/text().17",
)


class FakeFileRepository:
    """An in-memory EPUB store that counts reads.

    Structurally a ``FileRepositoryProtocol``; only ``get_epub`` is exercised,
    but the whole surface is implemented so the adapter can be constructed
    exactly as the container constructs it.
    """

    def __init__(self, epubs: dict[str, bytes]) -> None:
        self.epubs = epubs
        self.reads: list[str | None] = []

    async def get_epub(self, filename: str | None) -> bytes | None:
        self.reads.append(filename)
        return self.epubs.get(filename or "")

    async def save_epub(self, filename: str, content: bytes) -> str:
        self.epubs[filename] = content
        return filename

    async def delete_epub(self, filename: str | None) -> bool:
        return self.epubs.pop(filename or "", None) is not None

    async def get_cover(self, filename: str | None) -> bytes | None:
        return None

    async def save_cover(self, filename: str, content: bytes) -> str:
        return filename

    async def delete_cover(self, filename: str | None) -> bool:
        return False


def reworded(epub: bytes, old: str, new: str) -> bytes:
    """Return the same EPUB with one word swapped -- a different edition of it.

    Rewriting the archive rather than patching bytes, because the entries are
    deflate-compressed and the text never appears in the file literally.
    """
    source = zipfile.ZipFile(io.BytesIO(epub))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            body = source.read(info.filename).decode().replace(old, new)
            target.writestr(info, body, info.compress_type)
    return out.getvalue()


@pytest.fixture
def epub() -> bytes:
    return (Path(__file__).parents[3] / "fixtures" / "minimal.epub").read_bytes()


@pytest.fixture
def files(epub: bytes) -> FakeFileRepository:
    return FakeFileRepository({EBOOK_FILE: epub})


@pytest.fixture
def anchors(files: FakeFileRepository) -> XPointCfiPositionAnchorService:
    """The adapter wired the way the container wires it."""
    return XPointCfiPositionAnchorService(file_repository=files)


def test_the_adapter_implements_both_ports(anchors: XPointCfiPositionAnchorService) -> None:
    """Structural conformance, checked by pyright rather than at runtime."""
    anchor_port: PositionAnchorServiceProtocol = anchors
    cache_port: PublicationCacheProtocol = anchors
    assert anchor_port is cache_port


class TestXPointToLocator:
    async def test_a_range_becomes_a_locator_quoting_the_highlighted_text(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)

        assert locator.href == "OEBPS/chapter1.xhtml"
        assert locator.type == "application/xhtml+xml"
        assert locator.text.highlight == REPEATED_SENTENCE_TEXT
        # The selector must name the *second* paragraph of the two identical
        # ones; #intro's children are h1, p, p, p, p.
        assert locator.locations.css_selector == "#intro > p:nth-child(4)"
        assert locator.text.before is not None
        assert locator.text.before.endswith("twice, and meant it both times.\n\n      \n")

    async def test_a_range_inside_inline_markup_selects_that_element(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, NESTED_EMPHASIS)

        assert locator.text.highlight == "the same sentence"
        assert locator.locations.css_selector == "#intro > p:nth-child(3) > em:nth-child(1)"

    async def test_a_single_position_is_a_caret_with_context_but_no_quote(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        point = XPoint.parse("/body/DocFragment[2]/body/div/p[1]/text().8")

        locator = await anchors.locator_for_xpoint(EBOOK_FILE, point)

        assert locator.href == "OEBPS/chapter2.xhtml"
        assert locator.text.highlight == ""
        assert locator.text.after is not None
        assert locator.text.after.startswith("arrived without ceremony.")
        assert locator.locations.progression is not None
        assert 0.0 < locator.locations.progression < 1.0

    async def test_the_readium_json_shape_uses_camel_case(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)

        payload = locator.to_dict()
        assert payload["href"] == "OEBPS/chapter1.xhtml"
        assert payload["locations"] == {
            "progression": locator.locations.progression,
            "cssSelector": "#intro > p:nth-child(4)",
        }
        assert payload["text"]["highlight"] == REPEATED_SENTENCE_TEXT  # type: ignore[index]

    async def test_an_xpoint_that_does_not_resolve_is_an_anchor_resolution_error(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        nowhere = XPoint.parse("/body/DocFragment[1]/body/div/p[99]/text().0")

        with pytest.raises(AnchorResolutionError):
            await anchors.locator_for_xpoint(EBOOK_FILE, nowhere)


class TestLocatorToXPoint:
    async def test_a_derived_locator_round_trips_to_the_range_it_came_from(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)

        match = await anchors.xpoint_range_for_locator(EBOOK_FILE, locator)

        # The library normalizes a bare `div` to `div[1]`; the position is the same.
        assert match.xpoints.start.xpath == "/body/div[1]/p[3]"
        assert match.xpoints.start.char_offset == 0
        assert match.xpoints.end.char_offset == 32
        assert match.confidence is AnchorConfidence.BOTH_CONTEXTS

    async def test_context_decides_which_occurrence_of_a_repeated_sentence_wins(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        """Without before/after the same quote also matches p[1], and does."""
        contextless = Locator(
            href="OEBPS/chapter1.xhtml",
            type="application/xhtml+xml",
            text=LocatorText(highlight=REPEATED_SENTENCE_TEXT),
        )

        match = await anchors.xpoint_range_for_locator(EBOOK_FILE, contextless)

        assert match.xpoints.start.xpath == "/body/div[1]/p[1]"
        assert match.confidence is AnchorConfidence.AMBIGUOUS

    async def test_a_weak_match_is_ordered_below_a_strong_one(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        """The grade exists so callers can set a floor with one comparison."""
        assert AnchorConfidence.AMBIGUOUS < AnchorConfidence.ONE_CONTEXT
        assert AnchorConfidence.ONE_CONTEXT < AnchorConfidence.BOTH_CONTEXTS

    async def test_a_locator_naming_no_resource_is_an_anchor_resolution_error(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        elsewhere = Locator(
            href="OEBPS/chapter9.xhtml",
            type="application/xhtml+xml",
            text=LocatorText(highlight=REPEATED_SENTENCE_TEXT),
        )

        with pytest.raises(AnchorResolutionError):
            await anchors.xpoint_range_for_locator(EBOOK_FILE, elsewhere)

    async def test_a_quote_that_is_nowhere_in_the_book_is_an_anchor_resolution_error(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        absent = Locator(
            href="OEBPS/chapter1.xhtml",
            type="application/xhtml+xml",
            text=LocatorText(highlight="a phrase this book has never contained anywhere"),
        )

        with pytest.raises(AnchorResolutionError):
            await anchors.xpoint_range_for_locator(EBOOK_FILE, absent)


class TestVerification:
    async def test_a_derived_anchor_verifies_against_the_stored_highlight_text(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        """Whitespace differs between crengine's export and the EPUB's DOM text."""
        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)

        assert anchors.verify_locator(locator, "The  lantern went\n out at midnight  ") is True

    async def test_an_anchor_covering_a_different_passage_is_rejected(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        """What a replaced EPUB looks like: the anchor resolved, to the wrong text."""
        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)

        assert anchors.verify_locator(locator, "Nothing else in the house moved") is False

    async def test_a_caret_verifies_only_against_empty_text(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        point = XPoint.parse("/body/DocFragment[2]/body/div/p[1]/text().8")
        locator = await anchors.locator_for_xpoint(EBOOK_FILE, point)

        assert anchors.verify_locator(locator, "") is True
        assert anchors.verify_locator(locator, "Morning") is False


class TestPublicationCache:
    async def test_a_books_epub_is_read_and_parsed_once_for_many_conversions(
        self, anchors: XPointCfiPositionAnchorService, files: FakeFileRepository
    ) -> None:
        """The point of the cache: a whole book's highlights cost one parse."""
        await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)
        await anchors.locator_for_xpoint_range(EBOOK_FILE, NESTED_EMPHASIS)
        await anchors.locator_for_xpoint(
            EBOOK_FILE, XPoint.parse("/body/DocFragment[2]/body/div/p[1]/text().8")
        )

        assert files.reads == [EBOOK_FILE]

    async def test_eviction_makes_the_next_conversion_use_the_replaced_file(
        self, anchors: XPointCfiPositionAnchorService, files: FakeFileRepository, epub: bytes
    ) -> None:
        """A re-upload keeps the filename, so only eviction can reveal new bytes."""
        await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)
        files.epubs[EBOOK_FILE] = reworded(epub, "lantern", "beacons")

        anchors.evict(EBOOK_FILE)
        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)

        assert locator.text.highlight == "The beacons went out at midnight"
        assert files.reads == [EBOOK_FILE, EBOOK_FILE]

    async def test_without_eviction_a_replaced_file_is_still_served_from_the_cache(
        self, anchors: XPointCfiPositionAnchorService, files: FakeFileRepository, epub: bytes
    ) -> None:
        """The failure the upload path's evict() call exists to prevent."""
        await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)
        files.epubs[EBOOK_FILE] = reworded(epub, "lantern", "beacons")

        locator = await anchors.locator_for_xpoint_range(EBOOK_FILE, REPEATED_SENTENCE)

        assert locator.text.highlight == REPEATED_SENTENCE_TEXT

    async def test_evicting_an_uncached_book_is_a_no_op(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        anchors.evict("never-parsed.epub")

    async def test_the_least_recently_used_publication_is_dropped_when_full(
        self, anchors: XPointCfiPositionAnchorService, files: FakeFileRepository, epub: bytes
    ) -> None:
        names = [f"book-{n}.epub" for n in range(PARSED_PUBLICATION_CACHE_SIZE + 1)]
        for name in names:
            files.epubs[name] = epub
            await anchors.locator_for_xpoint_range(name, REPEATED_SENTENCE)

        # The oldest fell out; everything after it is still resident.
        await anchors.locator_for_xpoint_range(names[0], REPEATED_SENTENCE)
        await anchors.locator_for_xpoint_range(names[-1], REPEATED_SENTENCE)

        assert files.reads == [*names, names[0]]

    async def test_a_book_with_no_stored_epub_is_an_anchor_resolution_error(
        self, anchors: XPointCfiPositionAnchorService
    ) -> None:
        with pytest.raises(AnchorResolutionError, match="No EPUB stored"):
            await anchors.locator_for_xpoint_range("missing.epub", REPEATED_SENTENCE)

    async def test_an_unparseable_epub_is_an_anchor_resolution_error(
        self, anchors: XPointCfiPositionAnchorService, files: FakeFileRepository
    ) -> None:
        files.epubs["broken.epub"] = b"not a zip archive at all"

        with pytest.raises(AnchorResolutionError, match="Cannot parse EPUB"):
            await anchors.locator_for_xpoint_range("broken.epub", REPEATED_SENTENCE)
