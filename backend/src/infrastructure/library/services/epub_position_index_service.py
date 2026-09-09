"""Infrastructure service for building document-order position indices from EPUB files."""

import logging
from io import BytesIO

from ebooklib import epub
from lxml import etree

from src.domain.common.value_objects.position_index import PositionIndex
from src.infrastructure.common.memory import trims_memory

logger = logging.getLogger(__name__)


class EpubPositionIndexService:
    """Builds a position index by walking EPUB DOM in document order."""

    @trims_memory
    def build_position_index(self, epub_content: bytes) -> PositionIndex:
        """
        Build a position index from an EPUB file.

        Walks all spine items in order, parsing each HTML document's DOM
        in document order, and assigns a sequential integer to each element.

        Args:
            epub_content: EPUB file content as bytes

        Returns:
            PositionIndex mapping (doc_fragment_index, xpath) -> element_index
        """
        book = epub.read_epub(BytesIO(epub_content))
        items_by_id = {item.id: item for item in book.get_items()}

        element_positions: dict[tuple[int, str], int] = {}
        current_index = 1

        for spine_index, (item_id, _linear) in enumerate(book.spine, start=1):
            item = items_by_id.get(item_id)
            if item is None:
                continue

            content = item.get_content()
            parser = etree.HTMLParser()
            tree = etree.fromstring(content, parser)
            root_tree = tree.getroottree()

            # Walk DOM in document order
            for element in tree.iter():
                if not isinstance(element.tag, str):
                    continue  # Skip comments, processing instructions

                element_xpath: str = root_tree.getpath(element)
                # lxml gives paths like /html/body/div[1]/p[2]
                # We need /body/div[1]/p[2] (strip /html prefix)
                if element_xpath.startswith("/html"):
                    element_xpath = element_xpath[len("/html") :]

                key = (spine_index, element_xpath)
                element_positions[key] = current_index
                current_index += 1

        logger.info(
            "Built position index from EPUB",
            extra={
                "total_elements": current_index - 1,
            },
        )

        return PositionIndex(element_positions)
