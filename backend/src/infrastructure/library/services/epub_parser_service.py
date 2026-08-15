"""Infrastructure service for parsing EPUB files."""

# pyright: reportPrivateUsage=false

import logging
from io import BytesIO
from typing import Any, NamedTuple, cast
from urllib.parse import unquote

import ebooklib
from ebooklib import epub
from lxml import etree  # pyright: ignore[reportAttributeAccessIssue]

from src.domain.library.entities.chapter import TocChapter
from src.infrastructure.common.memory import trims_memory

logger = logging.getLogger(__name__)


class _TocEntry(NamedTuple):
    """A flattened TOC entry; `parent_index` points into the same flattened list."""

    title: str
    chapter_number: int
    parent_name: str | None
    parent_index: int | None
    href: str | None


def _extract_toc_hierarchy(
    toc_items: list[Any],
    entries: list[_TocEntry] | None = None,
    parent_name: str | None = None,
    parent_index: int | None = None,
) -> list[_TocEntry]:
    """
    Flatten the TOC tree into reading order, preserving parent relationships.

    Entries are appended to one shared list, so an entry's position in that list
    is its identity: children record the list index of their parent, which stays
    unambiguous when several chapters share a title.

    Args:
        toc_items: List of TOC items from ebooklib (can be Link objects or tuples)
        entries: Accumulator shared across recursion levels (None starts a new list)
        parent_name: Name of the parent chapter (None for root-level chapters)
        parent_index: Index of the parent entry in `entries` (None for root-level)

    Returns:
        The flattened list of TOC entries in reading order.
    """
    if entries is None:
        entries = []

    for item in toc_items:
        if isinstance(item, tuple):
            section, children = item[0], item[1] if len(item) > 1 else []

            if hasattr(section, "title"):
                section_index = len(entries)
                entries.append(
                    _TocEntry(
                        title=section.title,
                        chapter_number=section_index + 1,
                        parent_name=parent_name,
                        parent_index=parent_index,
                        href=getattr(section, "href", None),
                    )
                )
                section_name = section.title
            else:
                # Untitled section: its children hang off the enclosing parent.
                section_name = parent_name
                section_index = parent_index

            _extract_toc_hierarchy(children, entries, section_name, section_index)

        elif hasattr(item, "title"):
            entries.append(
                _TocEntry(
                    title=item.title,
                    chapter_number=len(entries) + 1,
                    parent_name=parent_name,
                    parent_index=parent_index,
                    href=getattr(item, "href", None),
                )
            )

    return entries


class EpubParserService:
    """Infrastructure service for parsing EPUB files."""

    @trims_memory
    def validate_epub(self, content: bytes) -> bool:
        """
        Validate epub file using ebooklib.

        Args:
            content: The file content as bytes

        Returns:
            True if valid epub, False otherwise
        """
        try:
            epub_file = BytesIO(content)
            book = epub.read_epub(epub_file)

            if not book.get_metadata("DC", "title"):
                logger.warning("EPUB missing title metadata")

            return True

        except Exception as e:
            logger.error(f"EPUB validation failed: {e!s}")
            return False

    @trims_memory
    def parse_toc(self, epub_content: bytes) -> list[TocChapter]:
        """
        Parse table of contents from an EPUB file.

        Args:
            epub_content: EPUB file content as bytes

        Returns:
            List of TocChapter objects in reading order.
            Returns empty list if EPUB has no TOC or TOC is invalid.
        """
        try:
            book = epub.read_epub(BytesIO(epub_content))

            toc = book.toc

            if not toc:
                logger.info("EPUB has no table of contents")
                return []

            toc_entries = _extract_toc_hierarchy(toc)

            spine_mapping = self._build_href_to_spine_index(book)
            result: list[TocChapter] = []
            html_cache: dict[int, etree._Element] = {}

            # First pass: compute start_xpoints (with precise fragment resolution)
            start_xpoints: list[str | None] = []
            for entry in toc_entries:
                if entry.href:
                    xpoint = self._resolve_href_to_xpoint(
                        book, entry.href, spine_mapping, html_cache
                    )
                    start_xpoints.append(xpoint)
                else:
                    start_xpoints.append(None)

            # Second pass: compute end_xpoints (next chapter's start_xpoint)
            for i, entry in enumerate(toc_entries):
                start_xpoint = start_xpoints[i]
                end_xpoint = None
                for j in range(i + 1, len(start_xpoints)):
                    if start_xpoints[j] is not None:
                        end_xpoint = start_xpoints[j]
                        break
                result.append(
                    TocChapter(
                        name=entry.title,
                        chapter_number=entry.chapter_number,
                        parent_name=entry.parent_name,
                        parent_index=entry.parent_index,
                        start_xpoint=start_xpoint,
                        end_xpoint=end_xpoint,
                    )
                )

            logger.info(f"Parsed {len(result)} chapters from EPUB TOC")
            return result

        except Exception as e:
            logger.error(f"Failed to parse TOC from EPUB: {e!s}")
            return []

    @trims_memory
    def extract_cover(self, epub_content: bytes) -> bytes | None:
        """
        Extract cover image from an EPUB file.

        Tries three strategies in order:
        1. OPF metadata via get_metadata("OPF", "cover")
        2. Items with ITEM_COVER type
        3. Scanning OPF "meta" entries for cover reference (handles namespace issues)

        Returns None if no cover found or on any error.
        """
        try:
            book = epub.read_epub(BytesIO(epub_content))

            # Strategy 1: Check OPF metadata for cover item ID
            cover_meta = book.get_metadata("OPF", "cover")
            if cover_meta:
                cover_id = cover_meta[0][1].get("content", "") if cover_meta[0][1] else ""
                if cover_id:
                    item = book.get_item_with_id(cover_id)
                    if item:
                        content = item.get_content()
                        if content:
                            logger.info("Extracted cover from OPF metadata")
                            return bytes(content)

            # Strategy 2: Fall back to ITEM_COVER type
            cover_items = list(book.get_items_of_type(ebooklib.ITEM_COVER))
            if cover_items:
                content = cover_items[0].get_content()
                if content:
                    logger.info("Extracted cover from ITEM_COVER")
                    return bytes(content)

            # Strategy 3: Scan OPF "meta" entries for cover reference
            # ebooklib sometimes stores <meta name="cover" content="..."/> under
            # ("OPF", "meta") instead of ("OPF", "cover") due to XML namespace handling.
            opf_meta_entries = book.get_metadata("OPF", "meta")
            for _text, attrs in opf_meta_entries:
                if attrs.get("name") == "cover":
                    cover_id = attrs.get("content", "")
                    if cover_id:
                        item = book.get_item_with_id(cover_id)
                        if item:
                            content = item.get_content()
                            if content:
                                logger.info("Extracted cover from OPF meta scan")
                                return bytes(content)

            logger.info("No cover image found in EPUB")
            return None

        except Exception as e:
            logger.warning(f"Failed to extract cover from EPUB: {e!s}")
            return None

    @staticmethod
    def _build_href_to_spine_index(book: Any) -> dict[str, int]:  # noqa: ANN401
        """Build a mapping from spine item file names to 1-based spine indices.

        Stores multiple forms of each file name (full path, basename, and
        URL-encoded variants) to maximize matching against TOC hrefs.
        """
        mapping: dict[str, int] = {}
        spine_items = book.spine
        items_by_id = {item.id: item for item in book.get_items()}

        for idx, (item_id, _linear) in enumerate(spine_items, start=1):
            item = items_by_id.get(item_id)
            if item:
                file_name = item.file_name
                mapping[file_name] = idx
                basename = file_name.rsplit("/", 1)[-1] if "/" in file_name else file_name
                if basename not in mapping:
                    mapping[basename] = idx
        return mapping

    @staticmethod
    def _href_to_spine_index(href: str, mapping: dict[str, int]) -> int | None:
        """Resolve a TOC href to a spine index using the mapping.

        Tries multiple strategies: exact match, URL-decoded match, and basename match.
        ebooklib URL-decodes manifest hrefs (item.file_name) but leaves NCX content
        src attributes raw, so we need to try the decoded form too.
        """
        file_part = href.split("#", 1)[0]

        # Try exact match
        if file_part in mapping:
            return mapping[file_part]

        # Try URL-decoded match (NCX hrefs may be URL-encoded while file_name is decoded)
        decoded = unquote(file_part)
        if decoded != file_part and decoded in mapping:
            return mapping[decoded]

        # Try basename match
        basename = file_part.rsplit("/", 1)[-1] if "/" in file_part else file_part
        if basename in mapping:
            return mapping[basename]

        # Try URL-decoded basename
        decoded_basename = unquote(basename)
        if decoded_basename != basename:
            return mapping.get(decoded_basename)

        return None

    @staticmethod
    def _resolve_href_to_xpoint(
        book: Any,  # noqa: ANN401
        href: str,
        spine_mapping: dict[str, int],
        html_cache: dict[int, etree._Element],
    ) -> str | None:
        """Resolve a TOC href to a precise XPoint string."""
        parts = href.split("#", 1)
        file_part = parts[0]
        fragment_id = parts[1] if len(parts) > 1 else None

        spine_idx = EpubParserService._href_to_spine_index(file_part, spine_mapping)
        if spine_idx is None:
            spine_idx = EpubParserService._href_to_spine_index(href.split("#", 1)[0], spine_mapping)
            if spine_idx is None:
                return None

        base_xpoint = f"/body/DocFragment[{spine_idx}]/body"

        if not fragment_id:
            return base_xpoint

        if spine_idx not in html_cache:
            spine_index_0 = spine_idx - 1
            if spine_index_0 < 0 or spine_index_0 >= len(book.spine):
                return base_xpoint

            item_id = book.spine[spine_index_0][0]
            items_by_id = {item.id: item for item in book.get_items()}
            item = items_by_id.get(item_id)
            if item is None:
                return base_xpoint

            content = item.get_content()
            parser = etree.HTMLParser()
            html_cache[spine_idx] = etree.fromstring(content, parser)

        tree = html_cache[spine_idx]

        xpath_result = tree.xpath(f'//*[@id="{fragment_id}"]')
        if not isinstance(xpath_result, list) or not xpath_result:
            logger.warning(
                f"Fragment #{fragment_id} not found in spine item {spine_idx}, "
                f"falling back to body-level XPoint"
            )
            return base_xpoint

        element = cast(etree._Element, xpath_result[0])

        element_xpath: str = tree.getroottree().getpath(element)
        if element_xpath.startswith("/html"):
            element_xpath = element_xpath[len("/html") :]

        return f"/body/DocFragment[{spine_idx}]{element_xpath}"
