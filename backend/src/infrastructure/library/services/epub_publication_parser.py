"""Read an EPUB into the index a Readium Web Publication Manifest is rendered from."""

# pyright: reportPrivateUsage=false

import hashlib
import logging
import mimetypes
import posixpath
import zipfile
from collections.abc import Callable, Iterable, Mapping
from io import BytesIO
from typing import NamedTuple, cast
from urllib.parse import quote, unquote

from lxml import etree

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationLayout,
    PublicationMetadata,
    PublicationResource,
    TocEntry,
)
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.common.zip_members import read_bounded_member

logger = logging.getLogger(__name__)

CONTAINER_PATH = "META-INF/container.xml"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
_OPF_NS = "http://www.idpf.org/2007/opf"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"

_NAV_PROPERTY = "nav"

_NAMES_TOC = "contains(concat(' ', normalize-space(.), ' '), ' toc ')"
# Read as HTML, ``epub:type`` keeps its prefix rather than resolving to a
# namespace; it names a list of tokens, and any other attribute only guesses.
_TOC_NAV = f"//nav[@*[name()='epub:type'][{_NAMES_TOC}]]"
_ANY_TOC_NAV = f"//nav[@*[{_NAMES_TOC}]]"

_FALLBACK_MEDIA_TYPE = "application/octet-stream"
# Publishers write this one often enough that every reader corrects it.
_MEDIA_TYPE_CORRECTIONS = {"image/jpg": "image/jpeg"}

# EPUB states the same two layouts twice over: once for the publication as a
# metadata value, and per spine item as an itemref property, spelled differently.
_LAYOUT_BY_RENDITION_VALUE = {
    "pre-paginated": PublicationLayout.FIXED,
    "reflowable": PublicationLayout.REFLOWABLE,
}
_LAYOUT_BY_ITEMREF_PROPERTY = {
    "rendition:layout-pre-paginated": PublicationLayout.FIXED,
    "rendition:layout-reflowable": PublicationLayout.REFLOWABLE,
}

# A package document lists one item per archive member, so at a generous 200
# bytes an item even a ten-thousand-file book writes about 2 MB of one.
MAX_STRUCTURAL_DOCUMENT_BYTES = 16 * 1024 * 1024


class _ManifestItem(NamedTuple):
    """One ``<item>`` of the package document's manifest."""

    item_id: str
    file_name: str
    media_type: str
    properties: tuple[str, ...]


class _PackageDocument(NamedTuple):
    """One parsed OPF: where it sits in the container, and everything an index is made of."""

    directory: str
    metadata: PublicationMetadata
    items: tuple[_ManifestItem, ...]
    spine: tuple[str, ...]
    spine_layouts: Mapping[str, PublicationLayout | None]
    ncx_id: str | None


class _NavigationSource(NamedTuple):
    """The member a publication's table of contents is written in, and the reader for it."""

    file_name: str
    parse: Callable[[bytes, str], tuple[TocEntry, ...]]


def read_publication(epub_content: bytes) -> ParsedPublication:
    """Resolve an EPUB into its reading order, resources, table of contents and metadata.

    Raises:
        InvalidEbookError: If the bytes are not a readable EPUB, its package
            document is missing, oversized or unparseable, or its spine names
            nothing the publication contains.
    """
    try:
        with zipfile.ZipFile(BytesIO(epub_content)) as archive:
            package = _read_package_document(archive)
            toc = _read_navigation(archive, package)
            sizes = {entry.filename: entry.file_size for entry in archive.infolist()}
    except InvalidEbookError:
        raise
    except Exception as e:
        raise InvalidEbookError(f"unreadable package document: {e!s}", "epub") from e

    items_by_id = {item.item_id: item for item in package.items}
    spine_ids = [idref for idref in package.spine if idref in items_by_id]
    reading_order = _resources(
        (items_by_id[idref] for idref in spine_ids),
        package.directory,
        sizes,
        layouts=package.spine_layouts,
    )
    if not reading_order:
        raise InvalidEbookError("has no readable spine items", "epub")

    in_spine = set(spine_ids)
    # Layout is a property of a reading-order item, so what is merely served
    # alongside carries none even where the publication states one.
    resources = _resources(
        (item for item in package.items if item.item_id not in in_spine),
        package.directory,
        sizes,
        layouts={},
    )

    logger.info(
        f"Parsed publication: {len(reading_order)} reading-order items, {len(resources)} resources"
    )
    return ParsedPublication(
        metadata=package.metadata,
        reading_order=reading_order,
        resources=resources,
        toc=toc,
        content_hash=hashlib.sha256(epub_content).hexdigest(),
    )


def _read_package_document(archive: zipfile.ZipFile) -> _PackageDocument:
    container = etree.fromstring(_read_structural_document(archive, CONTAINER_PATH))
    rootfile = container.find(f".//{{{_CONTAINER_NS}}}rootfile")
    opf_path = rootfile.get("full-path") if rootfile is not None else None
    if not opf_path:
        raise InvalidEbookError("container.xml names no package document", "epub")

    return _parse_package_document(
        etree.fromstring(_read_structural_document(archive, opf_path)),
        posixpath.dirname(opf_path),
    )


def _read_structural_document(archive: zipfile.ZipFile, name: str) -> bytes:
    # The cap turns away a member that honestly says it is too big; the bounded
    # read stops a member that lies about its size from inflating anyway.
    try:
        entry = archive.getinfo(posixpath.normpath(name))
    except KeyError as e:
        raise InvalidEbookError(f"is missing {name!r}", "epub") from e
    if entry.file_size > MAX_STRUCTURAL_DOCUMENT_BYTES:
        raise InvalidEbookError(
            f"{entry.filename!r} declares {entry.file_size} bytes, over the "
            f"{MAX_STRUCTURAL_DOCUMENT_BYTES} limit",
            "epub",
        )
    return read_bounded_member(archive, entry)


def _parse_package_document(package: etree._Element, directory: str) -> _PackageDocument:
    spine = package.find(f"{{{_OPF_NS}}}spine")
    return _PackageDocument(
        directory=directory,
        metadata=_metadata(package),
        items=_manifest_items(package),
        spine=tuple(
            idref
            for itemref in _children(spine, f"{{{_OPF_NS}}}itemref")
            if (idref := itemref.get("idref"))
        ),
        spine_layouts=_spine_layouts(spine, _default_layout(package)),
        ncx_id=(spine.get("toc") or None) if spine is not None else None,
    )


def _children(parent: etree._Element | None, tag: str) -> Iterable[etree._Element]:
    # Matching by tag keeps a comment or a processing instruction -- whose
    # ``tag`` is not a string at all -- from being read as an element.
    return parent.iterfind(tag) if parent is not None else ()


def _manifest_items(package: etree._Element) -> tuple[_ManifestItem, ...]:
    items: list[_ManifestItem] = []

    for element in _children(package.find(f"{{{_OPF_NS}}}manifest"), f"{{{_OPF_NS}}}item"):
        href = element.get("href")
        if not href:
            logger.warning(f"Dropped manifest item naming no file: {element.get('id')!r}")
            continue
        file_name = unquote(href)
        items.append(
            _ManifestItem(
                item_id=element.get("id") or "",
                file_name=file_name,
                media_type=_media_type(element.get("media-type"), file_name),
                properties=tuple((element.get("properties") or "").split()),
            )
        )

    return tuple(items)


def _media_type(declared: str | None, file_name: str) -> str:
    if declared:
        return _MEDIA_TYPE_CORRECTIONS.get(declared, declared)
    return mimetypes.guess_type(file_name.lower())[0] or _FALLBACK_MEDIA_TYPE


def _metadata(package: etree._Element) -> PublicationMetadata:
    values: dict[str, list[etree._Element]] = {}

    for element in _children(package.find(f"{{{_OPF_NS}}}metadata"), f"{{{_DC_NS}}}*"):
        values.setdefault(str(element.tag).rpartition("}")[2], []).append(element)

    return PublicationMetadata(
        title=_first_metadata(values, "title"),
        author=_first_metadata(values, "creator"),
        language=_first_metadata(values, "language"),
        identifier=_identifier(package.get("unique-identifier"), values.get("identifier", [])),
    )


def _first_metadata(values: dict[str, list[etree._Element]], name: str) -> str | None:
    entries = values.get(name)
    return entries[0].text if entries and entries[0].text else None


def _identifier(unique_id: str | None, identifiers: list[etree._Element]) -> str | None:
    # The package says which of a book's several identifiers it *is*, so position
    # says nothing; a stand-in invented here would rename the book on every parse.
    designated = next(
        (
            element.text
            for element in identifiers
            if element.get("id") == unique_id and element.text
        ),
        None,
    )
    if designated is not None:
        return designated
    return identifiers[0].text if identifiers and identifiers[0].text else None


def _default_layout(package: etree._Element) -> PublicationLayout | None:
    for meta in _children(package.find(f"{{{_OPF_NS}}}metadata"), f"{{{_OPF_NS}}}meta"):
        # A meta carrying `refines` describes the one resource it names, not the
        # publication, so reading it here would let a chapter set the book's layout.
        if meta.get("property") == "rendition:layout" and meta.get("refines") is None:
            return _LAYOUT_BY_RENDITION_VALUE.get((meta.text or "").strip())
    return None


def _spine_layouts(
    spine: etree._Element | None, default: PublicationLayout | None
) -> dict[str, PublicationLayout | None]:
    layouts: dict[str, PublicationLayout | None] = {}

    for itemref in _children(spine, f"{{{_OPF_NS}}}itemref"):
        if not (idref := itemref.get("idref")):
            continue
        layouts[idref] = default
        for prop in (itemref.get("properties") or "").split():
            if layout := _LAYOUT_BY_ITEMREF_PROPERTY.get(prop):
                layouts[idref] = layout

    return layouts


def _container_path(opf_dir: str, file_name: str) -> str | None:
    # A path that leaves the container names something the publication does not
    # hold; under the manifest's own URL a leading ``//`` even names another host.
    resolved = posixpath.normpath(posixpath.join(opf_dir, file_name))
    if resolved.startswith(("/", "../")) or resolved == "..":
        return None
    return resolved


def _resources(
    items: Iterable[_ManifestItem],
    opf_dir: str,
    sizes: dict[str, int],
    layouts: Mapping[str, PublicationLayout | None],
) -> tuple[PublicationResource, ...]:
    resources: list[PublicationResource] = []

    for item in items:
        container_path = _container_path(opf_dir, item.file_name)
        if container_path is None:
            logger.warning(
                f"Dropped manifest item pointing outside the publication: {item.item_id!r}"
            )
            continue
        # A manifest is a promise: an entry whose size nobody knows would put a
        # 404 in the reading order, so it is dropped rather than published.
        size = sizes.get(container_path)
        if size is None:
            logger.warning(f"Dropped manifest item the archive does not hold: {container_path!r}")
            continue
        # Encoded exactly once, from the same resolved name the size was looked
        # up under, so it is byte-identical to a derived locator's href.
        resources.append(
            PublicationResource(
                href=quote(container_path, safe="/"),
                media_type=item.media_type,
                size=size,
                layout=layouts.get(item.item_id),
            )
        )

    return tuple(resources)


def _read_navigation(archive: zipfile.ZipFile, package: _PackageDocument) -> tuple[TocEntry, ...]:
    source = _navigation_source(package)
    if source is None:
        return ()

    member = posixpath.normpath(posixpath.join(package.directory, source.file_name))
    # Navigation the archive does not hold degrades like navigation that cannot
    # be read, rather than costing the book as a missing package document does.
    try:
        archive.getinfo(member)
    except KeyError:
        logger.warning(f"Publication names navigation it does not hold: {member!r}")
        return ()

    # Navigation that cannot be parsed costs the table of contents alone; one the
    # archive will not yield -- oversized, corrupt, lying about its size -- costs the book.
    try:
        return source.parse(_read_structural_document(archive, member), posixpath.dirname(member))
    except InvalidEbookError:
        raise
    except Exception as e:
        logger.warning(f"Publication navigation {member!r} could not be read: {e!s}")
        return ()


def _navigation_source(package: _PackageDocument) -> _NavigationSource | None:
    # A publication carrying both is read from the navigation document, which is
    # the one its own version defines.
    for item in package.items:
        if _NAV_PROPERTY in item.properties:
            return _NavigationSource(item.file_name, _parse_nav)

    for item in package.items:
        if item.item_id == package.ncx_id:
            return _NavigationSource(item.file_name, _parse_ncx)

    return None


def _parse_nav(document: bytes, nav_dir: str) -> tuple[TocEntry, ...]:
    # Read as HTML rather than as XML because that is what a navigation document
    # is served as, and a book whose nav is malformed XML still navigates.
    root = etree.fromstring(document, etree.HTMLParser(encoding="utf-8"))
    navs = cast(list[etree._Element], root.xpath(_TOC_NAV) or root.xpath(_ANY_TOC_NAV))
    if not navs:
        logger.warning("Navigation document states no table of contents")
        return ()

    ordered_list = navs[0].find("ol")
    return _nav_entries(ordered_list, nav_dir) if ordered_list is not None else ()


def _nav_entries(ordered_list: etree._Element, nav_dir: str) -> tuple[TocEntry, ...]:
    entries: list[TocEntry] = []

    for item in ordered_list.findall("li"):
        sublist = item.find("ol")
        link = item.find("a")
        href = link.get("href") if link is not None else None
        if sublist is not None:
            heading = link if link is not None else item.find("span")
            entries.append(
                TocEntry(
                    _text_content(heading) if heading is not None else "",
                    _entry_href(nav_dir, href),
                    _nav_entries(sublist, nav_dir),
                )
            )
        elif link is not None and href:
            entries.append(TocEntry(_text_content(link), _entry_href(nav_dir, href), ()))

    return tuple(entries)


def _text_content(element: etree._Element) -> str:
    return "".join(cast(Iterable[str], element.itertext()))


def _parse_ncx(document: bytes, ncx_dir: str) -> tuple[TocEntry, ...]:
    nav_map = etree.fromstring(document).find(f"{{{_NCX_NS}}}navMap")
    return _ncx_entries(nav_map, ncx_dir) if nav_map is not None else ()


def _ncx_entries(parent: etree._Element, ncx_dir: str) -> tuple[TocEntry, ...]:
    entries: list[TocEntry] = []

    for point in parent.iterfind(f"{{{_NCX_NS}}}navPoint"):
        label = point.find(f"{{{_NCX_NS}}}navLabel/{{{_NCX_NS}}}text")
        content = point.find(f"{{{_NCX_NS}}}content")
        entries.append(
            TocEntry(
                title=(label.text or "") if label is not None else "",
                href=_entry_href(ncx_dir, content.get("src") if content is not None else None),
                children=_ncx_entries(point, ncx_dir),
            )
        )

    return tuple(entries)


def _entry_href(base_dir: str, href: str | None) -> str | None:
    # A link is written relative to the document that writes it, and arrives
    # still encoded, so it is decoded once here and encoded once on the way out.
    if not href:
        return None
    path, _, fragment = href.partition("#")
    # A reference naming no member -- one carrying a scheme, or a fragment alone
    # -- would otherwise resolve to the directory the navigation sits in.
    if not path or ":" in path.partition("/")[0]:
        return None
    resolved = _container_path(base_dir, unquote(path))
    if resolved is None:
        # An entry whose href escapes links nowhere rather than being dropped: a
        # hostile link costs its own line and not the nesting under it.
        logger.warning(f"TOC entry pointing outside the publication links nowhere: {href!r}")
        return None
    encoded = quote(resolved, safe="/")
    return f"{encoded}#{quote(unquote(fragment), safe='')}" if fragment else encoded
