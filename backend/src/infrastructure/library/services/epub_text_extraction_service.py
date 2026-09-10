"""Infrastructure service for extracting text from EPUB files."""

# pyright: reportPrivateUsage=false, reportArgumentType=false
# pyright: reportReturnType=false, reportGeneralTypeIssues=false
# pyright: reportIndexIssue=false, reportAttributeAccessIssue=false
# pyright: reportCallIssue=false
# The above ignores are needed because lxml type stubs don't accurately
# represent xpath() return types which depend on the query string content.

import logging
from io import BytesIO

from ebooklib import epub
from lxml import etree

from src.domain.common.value_objects.xpoint import XPoint
from src.domain.library.exceptions import XPointNavigationError
from src.infrastructure.common.memory import trims_memory

logger = logging.getLogger(__name__)


class EpubTextExtractionService:
    """Infrastructure service for extracting text from EPUB files."""

    @trims_memory
    def extract_text(
        self,
        epub_content: bytes,
        start_xpoint: str,
        end_xpoint: str,
    ) -> str:
        """
        Extract text content between two XPoint positions in an EPUB.

        Args:
            epub_content: EPUB file content as bytes
            start_xpoint: KOReader xpoint string for start position
            end_xpoint: KOReader xpoint string for end position

        Returns:
            The text content between the two positions

        Raises:
            XPointNavigationError: If cannot navigate to xpoint in EPUB
        """
        # Parse XPoints using domain object
        start = XPoint.parse(start_xpoint)
        end = XPoint.parse(end_xpoint)

        # Load EPUB
        epub_book = epub.read_epub(BytesIO(epub_content))

        # Extract text based on whether positions are in same fragment
        if start.doc_fragment_index == end.doc_fragment_index:
            return self._extract_fragment_by_char_range(
                epub_book, start.doc_fragment_index, start, end
            )
        return self._extract_across_fragments(epub_book, start, end)

    def _extract_fragment_by_element_range(
        self,
        epub_book: epub.EpubBook,
        fragment: int,
        start_xpoint: XPoint | None = None,
        end_xpoint: XPoint | None = None,
    ) -> str:
        """Extract text from a fragment, optionally bounded by start/end elements."""
        tree = self._get_spine_item_content(epub_book, fragment)
        body = tree.xpath("//body")
        if not body:
            return ""
        start_elem = self._find_element(tree, start_xpoint) if start_xpoint else None
        end_elem = self._find_element(tree, end_xpoint) if end_xpoint else None
        return self._extract_text_by_element_range(body[0], start_elem, end_elem)

    def _extract_fragment_by_char_range(
        self,
        book: epub.EpubBook,
        fragment: int,
        start: XPoint | None = None,
        end: XPoint | None = None,
    ) -> str:
        """Extract text from a fragment using char-offset precision."""
        tree = self._get_spine_item_content(book, fragment)
        body = tree.xpath("//body")
        if not body:
            return ""

        if start:
            start_elem = self._find_element(tree, start)
            start_target, start_attr = self._resolve_text_node_location(
                start_elem, start.text_node_index, tree
            )
            start_offset = start.char_offset
        else:
            start_target, start_attr, start_offset = None, None, 0

        if end:
            end_elem = self._find_element(tree, end)
            end_target, end_attr = self._resolve_text_node_location(
                end_elem, end.text_node_index, tree
            )
            end_offset = end.char_offset
        else:
            end_target, end_attr, end_offset = None, None, None

        return self._extract_between_locations(
            body[0],
            start_target,
            start_attr,
            start_offset,
            end_target,
            end_attr,
            end_offset,
        )

    def _get_full_fragment_content(self, epub_book: epub.EpubBook, fragment: int) -> str:
        tree = self._get_spine_item_content(epub_book, fragment)
        body = tree.xpath("//body")
        if body:
            return "".join(body[0].itertext())
        return ""

    @trims_memory
    def extract_chapter_text(
        self,
        epub_content: bytes,
        start_xpoint: str,
        end_xpoint: str | None,
    ) -> str:
        """Extract all text for a chapter defined by XPoints.

        Handles three cases:
        1. Same fragment: both XPoints in same spine item — extract element range
        2. Cross-fragment: XPoints in different spine items — element range + full fragments
        3. Last chapter (no end_xpoint): extract from start element to end of spine

        Args:
            epub_content: EPUB file content as bytes
            start_xpoint: XPoint string for chapter start
            end_xpoint: XPoint string for next chapter's start, or None for last chapter

        Returns:
            The full text content of the chapter
        """
        start = XPoint.parse(start_xpoint)
        end = XPoint.parse(end_xpoint) if end_xpoint else None

        epub_book = epub.read_epub(BytesIO(epub_content))

        start_frag = start.doc_fragment_index
        end_frag = end.doc_fragment_index if end else None

        # Case 1: Same fragment
        if end is not None and start_frag == end_frag:
            return self._extract_fragment_by_element_range(epub_book, start_frag, start, end)

        # Case 2+3: Cross-fragment or last chapter
        result_parts: list[str] = []

        # First fragment: from start element to end of fragment
        result_parts.append(
            self._extract_fragment_by_element_range(epub_book, start_frag, start_xpoint=start)
        )

        # Middle + remaining fragments
        last_frag = end_frag if end_frag is not None else len(epub_book.spine) + 1
        for frag_idx in range(start_frag + 1, last_frag):
            result_parts.append(self._get_full_fragment_content(epub_book, frag_idx))

        # End fragment: partial extraction if end has precise xpath
        if end and end_frag is not None and end.xpath != "/body":
            result_parts.append(
                self._extract_fragment_by_element_range(epub_book, end_frag, end_xpoint=end)
            )

        return "".join(result_parts)

    def _get_spine_item_content(
        self,
        book: epub.EpubBook,
        fragment_index: int,
    ) -> etree._Element:
        """Get parsed HTML content for a spine item."""
        spine_index = fragment_index - 1

        if spine_index < 0 or spine_index >= len(book.spine):
            raise XPointNavigationError(
                f"DocFragment[{fragment_index}]",
                f"index out of range (spine has {len(book.spine)} items)",
            )

        item_id = book.spine[spine_index][0]
        item = book.get_item_with_id(item_id)

        if item is None:
            raise XPointNavigationError(
                f"DocFragment[{fragment_index}]",
                f"spine item '{item_id}' not found in EPUB",
            )

        content = item.get_content()
        parser = etree.HTMLParser()
        return etree.fromstring(content, parser)

    def _convert_xpath(self, xpath: str) -> str:
        """Convert xpoint xpath to lxml-compatible xpath."""
        if xpath.startswith("/body"):
            return "//body" + xpath[5:]
        return xpath

    def _find_element(self, tree: etree._Element, xpoint: XPoint) -> etree._Element:
        """Find element by xpath, raising XPointNavigationError if not found."""
        xpath = self._convert_xpath(xpoint.xpath)
        elements = tree.xpath(xpath)
        if not elements:
            raise XPointNavigationError(
                f"{xpoint.xpath}/text().{xpoint.char_offset}",
                f"XPath '{xpoint.xpath}' matched no elements",
            )
        return elements[0]

    def _resolve_text_node_location(
        self,
        element: etree._Element,
        text_node_index: int,
        root: etree._Element | None = None,
    ) -> tuple[etree._Element, str]:
        """Resolve a 1-based text node index to (element, attribute) pair."""
        current_idx = 1

        if element.text:
            if current_idx == text_node_index:
                return element, "text"
            current_idx += 1

        for child in element:
            if child.tail:
                if current_idx == text_node_index:
                    return child, "tail"
                current_idx += 1

        if current_idx == 1 and text_node_index == 1 and root is not None:
            next_loc = self._find_next_text_node(root, element)
            if next_loc:
                return next_loc

        raise XPointNavigationError(
            f"text()[{text_node_index}]",
            f"text node index out of range (element has {current_idx - 1} text nodes)",
        )

    def _find_next_text_node(
        self, root: etree._Element, start_from: etree._Element
    ) -> tuple[etree._Element, str] | None:
        """Find the next text node in document order starting after start_from."""
        found_start = False
        for elem in root.iter():
            if elem == start_from:
                found_start = True
                if elem.tail:
                    return elem, "tail"
                continue

            if found_start:
                if elem.text:
                    return elem, "text"
                if elem.tail:
                    return elem, "tail"
        return None

    def _iter_text_locations(self, root: etree._Element) -> list[tuple[etree._Element, str, str]]:
        """Iterate through all text content in document order."""
        locations = []
        for elem in root.iter():
            if elem.text:
                locations.append((elem, "text", elem.text))
            if elem.tail:
                locations.append((elem, "tail", elem.tail))
        return locations

    def _extract_between_locations(
        self,
        root: etree._Element,
        start_elem: etree._Element | None,
        start_attr: str | None,
        start_offset: int,
        end_elem: etree._Element | None,
        end_attr: str | None,
        end_offset: int | None,
    ) -> str:
        """Extract text between two resolved locations in document order."""
        result_parts = []
        capturing = start_elem is None

        for elem, attr, text in self._iter_text_locations(root):
            if not capturing:
                if elem == start_elem and attr == start_attr:
                    capturing = True
                    if end_elem is not None and elem == end_elem and attr == end_attr:
                        result_parts.append(text[start_offset:end_offset])
                        break
                    result_parts.append(text[start_offset:])
            elif end_elem is not None and elem == end_elem and attr == end_attr:
                result_parts.append(text[:end_offset])
                break
            else:
                result_parts.append(text)

        return "".join(result_parts)

    def _extract_across_fragments(
        self,
        book: epub.EpubBook,
        start: XPoint,
        end: XPoint,
    ) -> str:
        """Extract text when start and end are in different DocFragments."""
        result_parts = [
            self._extract_fragment_by_char_range(book, start.doc_fragment_index, start=start)
        ]

        for frag_idx in range(start.doc_fragment_index + 1, end.doc_fragment_index):
            result_parts.append(self._get_full_fragment_content(book, frag_idx))

        result_parts.append(
            self._extract_fragment_by_char_range(book, end.doc_fragment_index, end=end)
        )

        return "".join(result_parts)

    def _extract_text_by_element_range(
        self,
        body: etree._Element,
        start_elem: etree._Element | None,
        end_elem: etree._Element | None,
    ) -> str:
        """Extract text from elements in document order between start and end elements."""
        if start_elem is not None and start_elem is end_elem:
            return "".join(start_elem.itertext())

        all_elements = list(body.iter())

        if start_elem is not None:
            try:
                start_idx = all_elements.index(start_elem)
            except ValueError:
                start_idx = 0
        else:
            start_idx = 0

        if end_elem is not None:
            try:
                end_idx = all_elements.index(end_elem)
            except ValueError:
                end_idx = len(all_elements)
        else:
            end_idx = len(all_elements)

        elements_in_range = set(all_elements[start_idx:end_idx])

        result_parts: list[str] = []
        for elem, _attr, text in self._iter_text_locations(body):
            if elem in elements_in_range:
                result_parts.append(text)

        return "".join(result_parts)
