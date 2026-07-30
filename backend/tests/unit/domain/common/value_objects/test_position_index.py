"""Tests for PositionIndex resolution."""

import pytest

from src.domain.common.value_objects.position import Position
from src.domain.common.value_objects.position_index import (
    PositionIndex,
    _normalize_xpath,  # pyright: ignore[reportPrivateUsage]
)


class TestPositionIndex:
    def test_resolve_simple_xpoint(self) -> None:
        index = PositionIndex({(1, "/body/div/p"): 5})
        pos = index.resolve("/body/DocFragment[1]/body/div/p")
        assert pos == Position(index=5, char_index=0)

    def test_resolve_with_char_offset(self) -> None:
        index = PositionIndex({(1, "/body/div/p"): 5})
        pos = index.resolve("/body/DocFragment[1]/body/div/p/text().42")
        assert pos == Position(index=5, char_index=42)

    def test_resolve_without_doc_fragment(self) -> None:
        index = PositionIndex({(1, "/body/div/p"): 5})
        pos = index.resolve("/body/div/p")
        assert pos == Position(index=5, char_index=0)

    def test_resolve_unknown_returns_none(self) -> None:
        index = PositionIndex({(1, "/body/div/p"): 5})
        pos = index.resolve("/body/DocFragment[2]/body/div/p")
        assert pos is None

    def test_resolve_invalid_xpoint_returns_none(self) -> None:
        index = PositionIndex({(1, "/body/div/p"): 5})
        pos = index.resolve("garbage")
        assert pos is None

    def test_ordering_across_fragments(self) -> None:
        index = PositionIndex(
            {
                (1, "/body/p"): 3,
                (2, "/body/p"): 10,
            }
        )
        pos1 = index.resolve("/body/DocFragment[1]/body/p")
        pos2 = index.resolve("/body/DocFragment[2]/body/p")
        assert pos1 is not None
        assert pos2 is not None
        assert pos1 < pos2


class TestPositionIndexXpathNormalization:
    """The index is built from lxml xpaths (always indexed) but queried with
    KOReader xpoints (which omit [1]), so the two forms must resolve alike."""

    def test_bare_xpoint_resolves_against_indexed_key(self) -> None:
        index = PositionIndex({(1, "/body/div[1]/p[1]"): 7})
        pos = index.resolve("/body/DocFragment[1]/body/div/p")
        assert pos == Position(index=7, char_index=0)

    def test_indexed_xpoint_resolves_against_bare_key(self) -> None:
        index = PositionIndex({(1, "/body/div/p"): 7})
        pos = index.resolve("/body/DocFragment[1]/body/div[1]/p[1]")
        assert pos == Position(index=7, char_index=0)

    def test_mixed_bare_and_indexed_segments(self) -> None:
        index = PositionIndex({(1, "/body/div[1]/p[3]/span[1]"): 9})
        pos = index.resolve("/body/DocFragment[1]/body/div/p[3]/span")
        assert pos == Position(index=9, char_index=0)

    def test_siblings_keep_distinct_positions(self) -> None:
        index = PositionIndex({(1, "/body/div[1]/p[1]"): 4, (1, "/body/div[1]/p[2]"): 8})
        assert index.resolve("/body/DocFragment[1]/body/div/p") == Position(index=4, char_index=0)
        assert index.resolve("/body/DocFragment[1]/body/div/p[2]") == Position(
            index=8, char_index=0
        )

    def test_explicit_index_is_never_rewritten_to_one(self) -> None:
        index = PositionIndex({(1, "/body/div[1]/p[2]"): 8})
        assert index.resolve("/body/DocFragment[1]/body/div/p") is None


class TestNormalizeXpath:
    @pytest.mark.parametrize(
        ("xpath", "expected"),
        [
            ("/body/div/p", "/body[1]/div[1]/p[1]"),
            ("/body/div[1]/p[1]", "/body[1]/div[1]/p[1]"),
            ("/body/div[2]/p[13]", "/body[1]/div[2]/p[13]"),
            ("/body/div/p[3]/span", "/body[1]/div[1]/p[3]/span[1]"),
            ("/body/my-widget/x_1", "/body[1]/my-widget[1]/x_1[1]"),
            ("/body//p", "/body[1]//p[1]"),
            ("/body/text()/p", "/body[1]/text()/p[1]"),
            ("/body/2col/p", "/body[1]/2col/p[1]"),
            ("", ""),
        ],
    )
    def test_normalization(self, xpath: str, expected: str) -> None:
        assert _normalize_xpath(xpath) == expected

    def test_normalization_is_idempotent(self) -> None:
        once = _normalize_xpath("/body/div/p[2]")
        assert _normalize_xpath(once) == once
