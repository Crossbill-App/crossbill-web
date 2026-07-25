"""Tests for XPoint value objects."""

import pytest

from src.domain.common.exceptions import XPointParseError
from src.domain.common.value_objects.xpoint import XPoint, XPointRange


class TestXPoint:
    """Test suite for XPoint parsing and operations."""

    def test_parse_simple_xpoint(self) -> None:
        """Parse xpoint without DocFragment defaults to fragment 1."""
        result = XPoint.parse("/body/div[1]/p[5]/text()[1].42")

        assert result.doc_fragment_index == 1
        assert result.xpath == "/body/div[1]/p[5]"
        assert result.text_node_index == 1
        assert result.char_offset == 42

    def test_parse_xpoint_with_doc_fragment(self) -> None:
        """Parse xpoint with DocFragment."""
        result = XPoint.parse("/body/DocFragment[12]/body/div/p[88]/text().223")

        assert result.doc_fragment_index == 12
        assert result.xpath == "/body/div/p[88]"
        assert result.text_node_index == 1  # Default when not specified
        assert result.char_offset == 223

    def test_parse_xpoint_with_explicit_text_node_index(self) -> None:
        """Parse xpoint with explicit text node index."""
        result = XPoint.parse("/body/div/p/text()[3].100")

        assert result.doc_fragment_index == 1
        assert result.xpath == "/body/div/p"
        assert result.text_node_index == 3
        assert result.char_offset == 100

    def test_parse_xpoint_zero_offset(self) -> None:
        """Parse xpoint with zero character offset."""
        result = XPoint.parse("/body/div/p/text().0")

        assert result.char_offset == 0

    def test_parse_xpoint_complex_xpath(self) -> None:
        """Parse xpoint with complex nested xpath."""
        result = XPoint.parse(
            "/body/DocFragment[1]/body/div[2]/section[1]/article/p[15]/text()[2].50"
        )

        assert result.doc_fragment_index == 1
        assert result.xpath == "/body/div[2]/section[1]/article/p[15]"
        assert result.text_node_index == 2
        assert result.char_offset == 50

    def test_parse_element_boundary_without_text(self) -> None:
        """Parse xpoint pointing to element boundary (no /text().offset)."""
        result = XPoint.parse("/body/DocFragment[14]/body/a")

        assert result.doc_fragment_index == 14
        assert result.xpath == "/body/a"
        assert result.text_node_index == 1  # Default
        assert result.char_offset == 0  # Default

    def test_parse_element_boundary_simple(self) -> None:
        """Parse simple element boundary xpoint."""
        result = XPoint.parse("/body/div/p")

        assert result.doc_fragment_index == 1
        assert result.xpath == "/body/div/p"
        assert result.text_node_index == 1
        assert result.char_offset == 0

    def test_parse_element_boundary_with_index(self) -> None:
        """Parse element boundary with indexed element."""
        result = XPoint.parse("/body/div[3]/span[2]")

        assert result.doc_fragment_index == 1
        assert result.xpath == "/body/div[3]/span[2]"
        assert result.text_node_index == 1
        assert result.char_offset == 0

    @pytest.mark.parametrize(
        "xpoint",
        [
            "",
            "not an xpoint",
            "/body/div/p/text()",  # missing offset
            "/body div",  # whitespace
            "/body/div.5.10",  # multiple dots
            "/invalid/path",  # doesn't start with /body
        ],
    )
    def test_parse_invalid_xpoint_raises_error(self, xpoint: str) -> None:
        """Invalid xpoint formats raise XPointParseError."""
        with pytest.raises(XPointParseError):
            XPoint.parse(xpoint)

    def test_parse_image_element_with_offset(self) -> None:
        """Parse image element with offset (no /text())."""
        result = XPoint.parse("/body/DocFragment[20]/body/div/p[1]/img.0")

        assert result.doc_fragment_index == 20
        assert result.xpath == "/body/div/p[1]/img"
        assert result.text_node_index == 1
        assert result.char_offset == 0

    def test_parse_element_with_offset_no_text(self) -> None:
        """Parse element with offset but no /text() specifier."""
        result = XPoint.parse("/body/span.5")

        assert result.doc_fragment_index == 1
        assert result.xpath == "/body/span"
        assert result.text_node_index == 1
        assert result.char_offset == 5

    def test_parse_invalid_doc_fragment_index_zero(self) -> None:
        """DocFragment index < 1 raises error."""
        with pytest.raises(XPointParseError, match="DocFragment index must be >= 1"):
            XPoint.parse("/body/DocFragment[0]/body/div")

    def test_parse_invalid_text_node_index_zero(self) -> None:
        """Text node index < 1 raises error."""
        with pytest.raises(XPointParseError, match="text node index must be >= 1"):
            XPoint.parse("/body/div/text()[0].10")

    def test_parse_invalid_negative_offset(self) -> None:
        """Negative offset raises error."""
        with pytest.raises(XPointParseError):
            XPoint.parse("/body/div/text().-5")

    def test_parse_without_doc_fragment_defaults_to_1(self) -> None:
        """XPoints without DocFragment prefix (single-spine EPUBs) default to fragment 1."""
        result = XPoint.parse("/body/div[1]/p[5]/text()[1].42")
        assert result.doc_fragment_index == 1

    def test_to_string_simple_xpoint(self) -> None:
        """Convert XPoint back to string — always includes DocFragment."""
        xpoint = XPoint.parse("/body/div[1]/p[5]/text()[1].42")
        assert xpoint.to_string() == "/body/DocFragment[1]/body/div[1]/p[5]/text().42"

    def test_to_string_with_doc_fragment(self) -> None:
        """Convert XPoint with DocFragment to string."""
        xpoint = XPoint.parse("/body/DocFragment[12]/body/div/p[88]/text().223")
        assert xpoint.to_string() == "/body/DocFragment[12]/body/div/p[88]/text().223"

    def test_to_string_element_boundary(self) -> None:
        """Convert element boundary XPoint to string — always includes DocFragment."""
        xpoint = XPoint.parse("/body/div/p")
        assert xpoint.to_string() == "/body/DocFragment[1]/body/div/p"

    def test_to_dict_and_from_dict(self) -> None:
        """XPoint can be serialized to dict and back."""
        original = XPoint.parse("/body/DocFragment[12]/body/div/p[88]/text()[2].223")
        xpoint_dict = original.to_dict()
        restored = XPoint.from_dict(xpoint_dict)

        assert restored == original
        assert restored.doc_fragment_index == 12
        assert restored.xpath == "/body/div/p[88]"
        assert restored.text_node_index == 2
        assert restored.char_offset == 223


class TestXPointRange:
    """Test suite for XPointRange operations."""

    def test_xpoint_range_validation_invalid_order(self) -> None:
        """XPointRange validates that start comes before end."""
        with pytest.raises(ValueError, match="Start XPoint must come before end XPoint"):
            XPointRange.parse(
                "/body/DocFragment[5]/body/div/p[1]/text().0",
                "/body/DocFragment[2]/body/div/p[1]/text().0",
            )

    def test_xpoint_range_validation_same_element_invalid_offset(self) -> None:
        """XPointRange validates offsets in same element."""
        with pytest.raises(ValueError, match="Start offset must be <= end offset"):
            XPointRange.parse("/body/div/p/text().100", "/body/div/p/text().50")

    def test_xpoint_range_validation_invalid_text_node(self) -> None:
        """XPointRange validates text node indices."""
        with pytest.raises(ValueError, match="Start text node must be <= end text node"):
            XPointRange.parse("/body/div/p/text()[3].0", "/body/div/p/text()[1].0")

    def test_xpoint_range_to_dict_and_from_dict(self) -> None:
        """XPointRange can be serialized to dict and back."""
        original = XPointRange.parse(
            "/body/DocFragment[2]/body/div/p[1]/text().0",
            "/body/DocFragment[5]/body/div/p[10]/text().100",
        )
        range_dict = original.to_dict()
        restored = XPointRange.from_dict(range_dict)

        assert restored.start == original.start
        assert restored.end == original.end
