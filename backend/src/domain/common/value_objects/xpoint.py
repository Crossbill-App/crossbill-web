"""
XPoint value objects for EPUB position tracking.

XPoint = position within an EPUB document (chapter_index, element_path, character_offset)
Used by KOReader to identify precise locations in books.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from typing import Self

from src.domain.common.exceptions import XPointParseError


class XPointDict(TypedDict):
    """Dictionary representation of XPoint for JSON serialization."""

    doc_fragment_index: int
    xpath: str
    text_node_index: int
    char_offset: int


class XPointRangeDict(TypedDict):
    """Dictionary representation of XPointRange for JSON serialization."""

    start: XPointDict
    end: XPointDict


# Regex pattern for parsing xpoint strings
# Format: /body/DocFragment[N]/body/.../text()[N].offset
# Or: /body/DocFragment[N]/body/... (element boundary, defaults to offset 0)
# Or: /body/DocFragment[N]/body/.../img.offset (for non-text elements like images)
# DocFragment, text node index, and text()/offset are optional
_XPOINT_PATTERN = re.compile(
    r"^"
    r"(?:/body/DocFragment\[(\d+)\])?"  # Optional DocFragment[N] - group 1
    r"(/body(?:/[^/.\s()]+)*)"  # XPath: /body followed by /element segments (no dots/parens)
    r"(?:"  # Optional offset section
    r"(?:/text\(\)(?:\[(\d+)\])?)?"  # Optional: text() with optional [N] - group 3
    r"\.(\d+)"  # .offset - group 4
    r")?"
    r"$"
)


@dataclass(frozen=True)
class XPoint:
    """Parsed representation of a KOReader xpoint string.

    XPoints are position references used by KOReader to mark locations in EPUB documents.
    Formats:
    - /body/DocFragment[12]/body/div/p[88]/text().223 (full format with offset)
    - /body/DocFragment[14]/body/a (element boundary, offset defaults to 0)
    - /body/DocFragment[20]/body/div/p[1]/img.0 (non-text element like image with offset)

    Attributes:
        doc_fragment_index: 1-based index into EPUB spine (defaults to 1)
        xpath: XPath to the element (without text() selector)
        text_node_index: 1-based index of text node within element (default 1)
        char_offset: 0-based character offset within text node (default 0)
    """

    doc_fragment_index: int
    xpath: str
    text_node_index: int
    char_offset: int

    @classmethod
    def parse(cls, xpoint: str) -> Self:
        """Parse an xpoint string into components.

        Formats supported:
        - /body/DocFragment[12]/body/div/p[88]/text().223
        - /body/div[1]/p[5]/text()[1].0
        - /body/div/p/text().42
        - /body/DocFragment[14]/body/a (element boundary, defaults to offset 0)
        - /body/DocFragment[20]/body/div/p[1]/img.0 (non-text element with offset)

        Args:
            xpoint: The xpoint string to parse

        Returns:
            ParsedXPoint with extracted components

        Raises:
            XPointParseError: If the format is invalid
        """
        match = _XPOINT_PATTERN.match(xpoint)
        if not match:
            raise XPointParseError(xpoint, "does not match expected xpoint format")

        doc_fragment_str, xpath, text_node_str, offset_str = match.groups()

        doc_fragment_index = int(doc_fragment_str) if doc_fragment_str else 1
        text_node_index = int(text_node_str) if text_node_str else 1
        # When /text().offset is omitted, default to offset 0 (element boundary)
        char_offset = int(offset_str) if offset_str else 0

        if doc_fragment_index < 1:
            raise XPointParseError(xpoint, "DocFragment index must be >= 1")

        if text_node_index < 1:
            raise XPointParseError(xpoint, "text node index must be >= 1")

        if char_offset < 0:
            raise XPointParseError(xpoint, "character offset must be >= 0")

        return cls(
            doc_fragment_index=doc_fragment_index,
            xpath=xpath,
            text_node_index=text_node_index,
            char_offset=char_offset,
        )

    def to_string(self) -> str:
        """
        Convert XPoint back to KOReader xpoint string format.

        Returns:
            XPoint string like "/body/DocFragment[12]/body/div/p[88]/text().223"
        """
        parts = []

        # Add DocFragment
        parts.append(f"/body/DocFragment[{self.doc_fragment_index}]")

        # Add xpath
        parts.append(self.xpath)

        # Add text node and offset if non-default
        if self.text_node_index != 1 or self.char_offset != 0:
            if self.text_node_index != 1:
                parts.append(f"/text()[{self.text_node_index}]")
            else:
                parts.append("/text()")
            parts.append(f".{self.char_offset}")

        return "".join(parts)

    @classmethod
    def from_dict(cls, data: XPointDict) -> Self:
        """
        Create XPoint from dictionary (for JSON deserialization).

        Args:
            data: Dictionary with keys: doc_fragment_index, xpath, text_node_index, char_offset

        Returns:
            XPoint instance
        """
        return cls(
            doc_fragment_index=data["doc_fragment_index"],
            xpath=data["xpath"],
            text_node_index=data.get("text_node_index", 1),
            char_offset=data.get("char_offset", 0),
        )

    def to_dict(self) -> XPointDict:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of XPoint
        """
        return {
            "doc_fragment_index": self.doc_fragment_index,
            "xpath": self.xpath,
            "text_node_index": self.text_node_index,
            "char_offset": self.char_offset,
        }


@dataclass(frozen=True)
class XPointRange:
    """
    Range between two XPoints for highlights.

    Represents the start and end position of highlighted text in an EPUB.
    """

    start: XPoint
    end: XPoint

    def __post_init__(self) -> None:
        """Validate that start comes before or at end position."""
        # Compare doc_fragment_index
        start_frag = self.start.doc_fragment_index
        end_frag = self.end.doc_fragment_index

        if start_frag > end_frag:
            raise ValueError("Start XPoint must come before end XPoint")

        # If same fragment, compare xpath and offsets
        if start_frag == end_frag and self.start.xpath == self.end.xpath:
            # Same element - compare text node and character offset
            if self.start.text_node_index > self.end.text_node_index:
                raise ValueError("Start text node must be <= end text node")
            if (
                self.start.text_node_index == self.end.text_node_index
                and self.start.char_offset > self.end.char_offset
            ):
                raise ValueError("Start offset must be <= end offset in same element")

    @classmethod
    def parse(cls, start_xpoint_str: str, end_xpoint_str: str) -> Self:
        """
        Parse XPointRange from two xpoint strings.

        Args:
            start_xpoint_str: Start xpoint string
            end_xpoint_str: End xpoint string

        Returns:
            XPointRange instance

        Raises:
            XPointParseError: If either xpoint string is invalid
        """
        return cls(
            start=XPoint.parse(start_xpoint_str),
            end=XPoint.parse(end_xpoint_str),
        )

    @classmethod
    def from_dict(cls, data: XPointRangeDict) -> Self:
        """Create XPointRange from dictionary (for JSON serialization)."""
        return cls(
            start=XPoint.from_dict(data["start"]),
            end=XPoint.from_dict(data["end"]),
        )

    def to_dict(self) -> XPointRangeDict:
        """Convert to dictionary for serialization."""
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
        }
