"""Infrastructure service for building document-order position indices from EPUB files."""

# pyright: reportPrivateUsage=false

import logging
from io import BytesIO

from ebooklib import epub
from lxml import etree

from src.domain.common.value_objects.position_index import ElementText, PositionIndex
from src.infrastructure.common.memory import trims_memory

logger = logging.getLogger(__name__)

_UNREAD_TAGS = frozenset({"head", "script", "style"})
_DOCUMENT_TYPES = frozenset({"application/xhtml+xml", "text/html"})


def _character_count(text: str | None) -> int:
    """Count a text node's characters, a whitespace run counting as one.

    A node of nothing but whitespace is markup layout rather than text, and counts zero.
    """
    if not text or text.isspace():
        return 0
    edges = int(text[0].isspace()) + int(text[-1].isspace())
    return len(" ".join(text.split())) + edges


class _Walk:
    """Numbers a book's elements in document order and counts their text."""

    _spine_index: int
    _root_tree: etree._ElementTree

    def __init__(self) -> None:
        self.element_positions: dict[tuple[int, str], int] = {}
        self.element_texts: dict[tuple[int, str], ElementText] = {}
        self.characters = 0
        self._next_index = 1

    def document(self, spine_index: int, root: etree._Element, counted: bool) -> None:
        self._spine_index = spine_index
        self._root_tree = root.getroottree()
        self._element(root, counted)

    def _text_node(self, text: str | None, counted: bool, nodes: list[tuple[int, int]]) -> None:
        if text is None:
            return
        length = _character_count(text) if counted else 0
        nodes.append((self.characters, length))
        self.characters += length

    def _element(self, element: etree._Element, counted: bool) -> None:
        counted = counted and element.tag not in _UNREAD_TAGS
        xpath: str = self._root_tree.getpath(element)
        # lxml gives /html/body/div[1]/p[2]; xpoints start at /body
        if xpath.startswith("/html"):
            xpath = xpath[len("/html") :]
        key = (self._spine_index, xpath)
        self.element_positions[key] = self._next_index
        self._next_index += 1

        start = self.characters
        nodes: list[tuple[int, int]] = []
        self._text_node(element.text, counted, nodes)
        for child in element:
            # The stubs type every tag as str, but a comment's is a function
            if isinstance(child.tag, str):  # pyright: ignore[reportUnnecessaryIsInstance]
                self._element(child, counted)
            self._text_node(child.tail, counted, nodes)
        self.element_texts[key] = ElementText(start, self.characters, tuple(nodes))


class EpubPositionIndexService:
    """Builds a position index by walking EPUB DOM in document order."""

    @trims_memory
    def build_position_index(self, epub_content: bytes) -> PositionIndex:
        """
        Build a position index from an EPUB file.

        Walks all spine items in order, parsing each HTML document's DOM
        in document order, and assigns a sequential integer to each element.
        Alongside, it counts the characters of the text a reader sees.

        Args:
            epub_content: EPUB file content as bytes

        Returns:
            PositionIndex mapping (doc_fragment_index, xpath) -> element_index
        """
        book = epub.read_epub(BytesIO(epub_content))
        items_by_id = {item.id: item for item in book.get_items()}

        walk = _Walk()
        for spine_index, (item_id, _linear) in enumerate(book.spine, start=1):
            item = items_by_id.get(item_id)
            if item is None:
                continue
            # An image in the spine still parses, and its bytes would count as text
            counted = item.media_type in _DOCUMENT_TYPES
            walk.document(
                spine_index, etree.fromstring(item.get_content(), etree.HTMLParser()), counted
            )

        logger.info(
            "Built position index from EPUB",
            extra={
                "total_elements": len(walk.element_positions),
                "total_characters": walk.characters,
            },
        )

        return PositionIndex(walk.element_positions, walk.element_texts, walk.characters)
