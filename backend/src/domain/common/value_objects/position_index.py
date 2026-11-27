"""PositionIndex - resolves xpoint strings to Position values."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.common.value_objects.position import Position
from src.domain.common.value_objects.xpoint import XPoint

# Matches an xpath segment like "body", "div", "p[2]" - captures tag name
# and optional bracket index.
_SEGMENT_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*)(\[\d+\])?$")


def _normalize_xpath(xpath: str) -> str:
    """Normalize an xpath by adding explicit [1] indices where omitted.

    lxml always produces explicit indices (e.g. /body/p[1]/span[1])
    while KOReader xpoints may omit [1] (e.g. /body/p/span).
    This function ensures both forms map to the same key.

    Args:
        xpath: XPath like "/body/div/p" or "/body/div[1]/p[2]"

    Returns:
        Normalized xpath like "/body/div[1]/p[1]" or "/body/div[1]/p[2]"
    """
    if not xpath:
        return xpath

    parts = xpath.split("/")
    normalized: list[str] = []
    for part in parts:
        if not part:
            normalized.append("")
            continue
        match = _SEGMENT_RE.match(part)
        if match:
            tag = match.group(1)
            index = match.group(2)
            if index is None:
                normalized.append(f"{tag}[1]")
            else:
                normalized.append(part)
        else:
            normalized.append(part)
    return "/".join(normalized)


@dataclass(frozen=True, slots=True)
class ElementText:
    """Where an element's text lies, in characters from the start of the book.

    ``start`` and ``end`` bound the element's whole text, its descendants'
    included. ``text_nodes`` holds ``(start, length)`` for each of the element's
    own text nodes in document order, so ``text()[N]`` is entry ``N - 1``.
    """

    start: int
    end: int
    text_nodes: tuple[tuple[int, int], ...] = ()


class PositionIndex:
    """Maps xpoint strings to document-order positions and character offsets.

    Built by infrastructure services (e.g., EpubPositionIndexService).
    Used by application layer use cases to assign positions to entities.
    """

    def __init__(
        self,
        element_positions: dict[tuple[int, str], int],
        element_texts: dict[tuple[int, str], ElementText] | None = None,
        total_characters: int = 0,
    ) -> None:
        """
        Args:
            element_positions: mapping from (doc_fragment_index, xpath) to element index.
                Xpaths are normalized (explicit [1] indices added) on construction.
            element_texts: mapping from the same keys to where each element's text lies.
            total_characters: the number of characters in the whole book.
        """
        self._element_positions = {
            (frag, _normalize_xpath(xpath)): idx for (frag, xpath), idx in element_positions.items()
        }
        self._element_texts = {
            (frag, _normalize_xpath(xpath)): text
            for (frag, xpath), text in (element_texts or {}).items()
        }
        self._total_characters = total_characters

    @property
    def total_characters(self) -> int:
        """Return the number of characters in the book."""
        return self._total_characters

    @property
    def total_elements(self) -> int:
        """Return the total number of elements in the index (max position value), or 0 if empty."""
        if not self._element_positions:
            return 0
        return max(self._element_positions.values())

    def resolve(self, xpoint_str: str) -> Position | None:
        """Resolve an xpoint string to a Position.

        Args:
            xpoint_str: xpoint string like "/body/DocFragment[14]/body/div[1]/p[3]/text().50"

        Returns:
            Position or None if the xpoint cannot be resolved
        """
        try:
            xpoint = XPoint.parse(xpoint_str)
        except Exception:
            return None

        doc_frag = xpoint.doc_fragment_index
        normalized_xpath = _normalize_xpath(xpoint.xpath)
        key = (doc_frag, normalized_xpath)

        element_index = self._element_positions.get(key)
        if element_index is None:
            return None

        char_index = xpoint.char_offset

        return Position(index=element_index, char_index=char_index)

    def character_offset(self, xpoint_str: str) -> int | None:
        """Count the characters from the start of the book to an xpoint.

        The xpoint's offset is clamped to the text it points into, so it never
        reaches past the end of its text node, or of its element when it names none.

        Returns:
            The offset, or None if the xpoint cannot be resolved
        """
        try:
            xpoint = XPoint.parse(xpoint_str)
        except Exception:
            return None

        text = self._element_texts.get((xpoint.doc_fragment_index, _normalize_xpath(xpoint.xpath)))
        if text is None:
            return None

        # XPoint defaults text_node_index to 1 for "p.0" too, and the element's
        # first text node can follow a child element, so only text() picks a node.
        if "/text()" in xpoint_str and xpoint.text_node_index <= len(text.text_nodes):
            start, length = text.text_nodes[xpoint.text_node_index - 1]
            return start + min(xpoint.char_offset, length)
        return text.start + min(xpoint.char_offset, text.end - text.start)
