"""Infrastructure service for parsing EPUB files."""

# pyright: reportPrivateUsage=false

import logging
import mimetypes
import posixpath
import struct
import zipfile
from collections.abc import Callable, Iterable
from io import BytesIO
from typing import Any, NamedTuple, cast
from urllib.parse import quote, unquote

import ebooklib
from ebooklib import epub
from lxml import etree  # pyright: ignore[reportAttributeAccessIssue]

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationLayout,
    PublicationMetadata,
    PublicationResource,
    TocEntry,
)
from src.domain.library.entities.chapter import TocChapter
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.common.memory import trims_memory
from src.infrastructure.common.zip_members import read_bounded_member

logger = logging.getLogger(__name__)

CONTAINER_PATH = "META-INF/container.xml"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
_OPF_NS = "http://www.idpf.org/2007/opf"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"

_XHTML_MEDIA_TYPE = "application/xhtml+xml"
_NCX_MEDIA_TYPE = "application/x-dtbncx+xml"
_FALLBACK_MEDIA_TYPE = "application/octet-stream"
# Publishers write this one often enough that every reader corrects it.
_MEDIA_TYPE_CORRECTIONS = {"image/jpg": "image/jpeg"}

# The manifest property naming the EPUB 3 navigation document.
_NAV_PROPERTY = "nav"

# EPUB spells the Readium layout property two ways: once for the publication, as
# a `rendition:layout` metadata value, and per spine item, as an itemref
# property. Both use the same two names under different spellings.
_LAYOUT_BY_RENDITION_VALUE = {
    "pre-paginated": PublicationLayout.FIXED,
    "reflowable": PublicationLayout.REFLOWABLE,
}
_LAYOUT_BY_ITEMREF_PROPERTY = {
    "rendition:layout-pre-paginated": PublicationLayout.FIXED,
    "rendition:layout-reflowable": PublicationLayout.REFLOWABLE,
}

# Serving a manifest parses whatever EPUB is stored for the book, and the upload
# limit bounds only the compressed bytes, so these bound the shape the archive
# declares for itself. Both are far above any real book: a heavily illustrated
# EPUB runs to a few hundred megabytes across a few thousand files.
MAX_PUBLICATION_ENTRIES = 10_000
MAX_PUBLICATION_UNCOMPRESSED_BYTES = 2 * 1024**3

# The largest container, package or navigation document this will read.
#
# The total above bounds the archive; this bounds each of the three members the
# parse actually decompresses, which is what the total cannot do -- 2 GiB of
# declared content is an ordinary illustrated library, and a single 2 GiB OPF is
# a bomb wearing the only file the parse cannot skip.
#
# Derived from the entry cap rather than picked: a package document lists one
# `<item>` per member, and at a generous 200 bytes an item, the largest manifest
# admitted here -- `MAX_PUBLICATION_ENTRIES` -- writes about 2 MB. A navigation
# document is the same shape and no denser: one line per entry. Eight times that
# leaves room for the outliers this must not turn away, an anthology's
# thousand-entry table of contents included, while sitting well under the
# `MAX_RESOURCE_BYTES` cap on a member that is merely served -- a document the
# parse must hold to answer at all is not the place for the loosest limit.
MAX_STRUCTURAL_DOCUMENT_BYTES = 16 * 1024 * 1024

# Offsets into the zip trailer records, from APPNOTE.TXT sections 4.3.14-4.3.16.
# Read by hand because the count has to be known before `zipfile` opens the file.
_EOCD_SIGNATURE = b"PK\x05\x06"
_EOCD_SIZE = 22
_EOCD_ENTRY_COUNT_OFFSET = 10
_EOCD_MAX_COMMENT = 0xFFFF
_ZIP64_SENTINEL = 0xFFFF
_ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
_ZIP64_LOCATOR_SIZE = 20
_ZIP64_LOCATOR_RECORD_OFFSET = 8
_ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
_ZIP64_ENTRY_COUNT_OFFSET = 32


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


class _ManifestItem(NamedTuple):
    """One ``<item>`` of the package document's manifest.

    Attributes:
        item_id: The manifest ``id``, ``""`` for an item that states none -- such
            an item can never be named by a spine ``itemref``.
        file_name: The item's path relative to the package document, decoded
            exactly once (see :func:`_container_href`).
        media_type: The declared media type, corrected or guessed when the
            package document leaves it out.
        properties: The manifest properties, split on whitespace.
    """

    item_id: str
    file_name: str
    media_type: str
    properties: tuple[str, ...]


class _NavPoint(NamedTuple):
    """One line of a navigation document or NCX, with the lines nested under it.

    The intermediate between the two navigation formats and :class:`TocEntry`:
    an href here is still written as the document wrote it -- percent-encoded,
    possibly carrying a fragment -- and is resolved against the container root
    only in :func:`_toc_entries`.

    Attributes:
        title: The entry's text, ``""`` for an entry that states none.
        href: Where it points, ``""`` for a heading that links nowhere.
        children: The entries nested below this one, in reading order.
    """

    title: str
    href: str
    children: tuple["_NavPoint", ...]


class _PackageDocument(NamedTuple):
    """The OPF, read directly rather than through a library that reads the book.

    Everything a manifest needs is stated *in* the package document; nothing
    about it requires reading the files it names. Keeping that true is the point
    of this type: a publication is resolved from three small documents -- the
    container, the OPF, and one navigation document -- however much content the
    archive holds (#773).

    Attributes:
        directory: The package document's directory inside the container, ``""``
            when the OPF sits at the container root.
        metadata: What the package says about the book itself.
        items: The manifest, in document order.
        spine: The reading order as ``idref``\\ s, dangling ones included.
        default_layout: The publication-wide ``rendition:layout``, if stated.
        layout_by_idref: Per-spine-item layout overrides, keyed by manifest id.
        ncx_id: The manifest id the spine's ``toc`` attribute names, if any.
    """

    directory: str
    metadata: PublicationMetadata
    items: tuple[_ManifestItem, ...]
    spine: tuple[str, ...]
    default_layout: PublicationLayout | None
    layout_by_idref: dict[str, PublicationLayout]
    ncx_id: str | None


def _declared_entry_count(epub_content: bytes) -> int | None:
    """Read how many entries the archive claims, without opening it.

    ``zipfile.ZipFile`` parses the whole central directory in its constructor
    and builds a ``ZipInfo`` per entry, so by the time :func:`infolist` could be
    consulted the allocation an entry limit exists to prevent has already
    happened: 200,000 empty members fit in a 17 MB archive and cost ~100 MB to
    open, and a file within the upload limit can declare several times that.
    The count therefore has to come from the End of Central Directory record,
    which sits in the last 64 KiB and costs one search.

    Returns:
        The declared total, or ``None`` when no EOCD record can be found -- in
        which case ``ZipFile`` will refuse the archive on its own terms.
    """
    tail_start = max(0, len(epub_content) - (_EOCD_SIZE + _EOCD_MAX_COMMENT))
    eocd = epub_content.rfind(_EOCD_SIGNATURE, tail_start)
    if eocd < 0 or eocd + _EOCD_SIZE > len(epub_content):
        return None

    (count,) = struct.unpack_from("<H", epub_content, eocd + _EOCD_ENTRY_COUNT_OFFSET)
    if count != _ZIP64_SENTINEL:
        return count
    # 0xFFFF is the "look in the ZIP64 record" sentinel, which any archive with
    # more than 65,535 entries must use -- exactly the ones this guard is for.
    return _zip64_entry_count(epub_content, eocd)


def _zip64_entry_count(epub_content: bytes, eocd: int) -> int | None:
    """Follow the ZIP64 locator that precedes ``eocd`` to the real entry count."""
    locator = eocd - _ZIP64_LOCATOR_SIZE
    if locator < 0 or not epub_content.startswith(_ZIP64_LOCATOR_SIGNATURE, locator):
        return None

    (record,) = struct.unpack_from("<Q", epub_content, locator + _ZIP64_LOCATOR_RECORD_OFFSET)
    if record + _ZIP64_ENTRY_COUNT_OFFSET + 8 > len(epub_content):
        return None
    if not epub_content.startswith(_ZIP64_EOCD_SIGNATURE, record):
        return None

    (count,) = struct.unpack_from("<Q", epub_content, record + _ZIP64_ENTRY_COUNT_OFFSET)
    return count


def _reject_overfull_archive(epub_content: bytes) -> None:
    """Refuse an archive that says it holds more members than a book could.

    Runs before :class:`zipfile.ZipFile` is constructed; see
    :func:`_declared_entry_count` for why that ordering is the whole point.

    Raises:
        InvalidEbookError: If the declared entry count is over the limit.
    """
    declared = _declared_entry_count(epub_content)
    if declared is not None and declared > MAX_PUBLICATION_ENTRIES:
        raise InvalidEbookError(
            f"declares {declared} entries, over the {MAX_PUBLICATION_ENTRIES} limit", "epub"
        )


def _reject_oversized_archive(archive: zipfile.ZipFile) -> None:
    """Refuse an archive whose parsed directory is far larger than a book.

    Read from the central directory, so this costs no decompression. It is a
    sanity check and not a decompression limit: the sizes an archive declares
    are attacker-controlled and a deliberate bomb can understate them. What it
    does buy is that a stored file which merely *claims* to expand to tens of
    gigabytes is turned away before ebooklib reads every entry into memory,
    which the compressed-bytes limit on upload cannot see.

    The entry count is checked again here against the members ``ZipFile``
    actually found, because an EOCD that understated the count would otherwise
    slip past :func:`_reject_overfull_archive`.

    Raises:
        InvalidEbookError: If the archive holds too many entries or declares too
            much uncompressed content.
    """
    entries = archive.infolist()
    if len(entries) > MAX_PUBLICATION_ENTRIES:
        raise InvalidEbookError(
            f"declares {len(entries)} entries, over the {MAX_PUBLICATION_ENTRIES} limit", "epub"
        )
    declared_bytes = sum(entry.file_size for entry in entries)
    if declared_bytes > MAX_PUBLICATION_UNCOMPRESSED_BYTES:
        raise InvalidEbookError(
            f"declares {declared_bytes} uncompressed bytes, over the "
            f"{MAX_PUBLICATION_UNCOMPRESSED_BYTES} limit",
            "epub",
        )


def _read_publication(epub_content: bytes) -> tuple[_PackageDocument, tuple[_NavPoint, ...]]:
    """Read a publication's structure, decompressing only the documents that hold it.

    Three members are read and no others: ``META-INF/container.xml``, the
    package document it names, and the navigation document (or NCX) the package
    names in turn. Sizes and names come from the central directory, which costs
    nothing to consult, so what a publication costs to resolve is a property of
    its structure rather than of its content -- and each of the three is read
    under :func:`_read_structural_document`, so being one of them is not a way
    to be read on trust.

    Raises:
        InvalidEbookError: If the archive is implausibly large, or the container
            or its package document is missing, oversized or unparseable.
    """
    _reject_overfull_archive(epub_content)
    try:
        with zipfile.ZipFile(BytesIO(epub_content)) as archive:
            _reject_oversized_archive(archive)
            container = etree.fromstring(_read_structural_document(archive, CONTAINER_PATH))
            rootfile = container.find(f".//{{{_CONTAINER_NS}}}rootfile")
            opf_path = rootfile.get("full-path") if rootfile is not None else None
            if not opf_path:
                raise InvalidEbookError("container.xml names no package document", "epub")
            package = _package_document(
                etree.fromstring(_read_structural_document(archive, opf_path)),
                posixpath.dirname(opf_path),
            )
            return package, _read_navigation(archive, package)
    except InvalidEbookError:
        raise
    except Exception as e:
        raise InvalidEbookError(f"unreadable package document: {e!s}", "epub") from e


def _read_structural_document(archive: zipfile.ZipFile, name: str) -> bytes:
    """Read one of the documents a publication's structure is written in.

    The declaration is checked before the read and enforced during it, in that
    order, because neither does the other's job: the cap turns away a member
    that honestly says it is too big, and the bounded read stops a member that
    lies from inflating anyway. Without the second, a member declaring eight
    bytes and holding two gigabytes passes the cap and then costs the two
    gigabytes -- ``ZipFile.read()`` truncates the result to the declaration and
    hands the decompressor no limit at all.

    Raises:
        InvalidEbookError: If the member is over the cap, unreadable, or carries
            more than it declared.
    """
    entry = archive.getinfo(posixpath.normpath(name))
    if entry.file_size > MAX_STRUCTURAL_DOCUMENT_BYTES:
        raise InvalidEbookError(
            f"{entry.filename!r} declares {entry.file_size} bytes, over the "
            f"{MAX_STRUCTURAL_DOCUMENT_BYTES} limit",
            "epub",
        )

    document = read_bounded_member(archive, entry)
    if len(document) > entry.file_size:
        raise InvalidEbookError(
            f"{entry.filename!r} carries more than the {entry.file_size} bytes it declares",
            "epub",
        )
    return document


def _package_document(package: etree._Element, directory: str) -> _PackageDocument:
    """Read everything a manifest is made of out of one parsed OPF."""
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
        default_layout=_default_layout(package),
        layout_by_idref=_layout_overrides(package),
        ncx_id=spine.get("toc") if spine is not None else None,
    )


def _children(parent: etree._Element | None, tag: str) -> Iterable[etree._Element]:
    """The matching child elements of an element that may not be there.

    Matching by tag rather than walking every child is what keeps a comment or a
    processing instruction -- whose ``tag`` is not a string at all -- from being
    read as an element of the publication.
    """
    return parent.iterfind(tag) if parent is not None else ()


def _manifest_items(package: etree._Element) -> tuple[_ManifestItem, ...]:
    """Read the manifest, dropping any item that names no file at all."""
    items: list[_ManifestItem] = []

    for element in _children(package.find(f"{{{_OPF_NS}}}manifest"), f"{{{_OPF_NS}}}item"):
        href = element.get("href")
        if not href:
            logger.warning(f"Dropped manifest item naming no file: {element.get('id')!r}")
            continue
        # Decoded exactly once, here, so that every later step works with the
        # file's real name -- the same reason `_container_href` encodes once.
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
    """The media type to publish for a manifest item.

    A publication is expected to declare one, and what it declares is what the
    manifest carries. An item that leaves it out is broken EPUB rather than an
    unservable file, so the extension answers instead -- a resource with no type
    at all could not be served under one.
    """
    if declared:
        return _MEDIA_TYPE_CORRECTIONS.get(declared, declared)
    return mimetypes.guess_type(file_name.lower())[0] or _FALLBACK_MEDIA_TYPE


def _metadata(package: etree._Element) -> PublicationMetadata:
    """Read the Dublin Core metadata the manifest publishes."""
    values: dict[str, list[tuple[str | None, str | None]]] = {}

    for element in _children(package.find(f"{{{_OPF_NS}}}metadata"), f"{{{_DC_NS}}}*"):
        name = element.tag.rpartition("}")[2]
        values.setdefault(name, []).append((element.text, element.get("id")))

    return PublicationMetadata(
        title=_first_metadata(values, "title"),
        author=_first_metadata(values, "creator"),
        language=_first_metadata(values, "language"),
        identifier=_identifier(package, values.get("identifier", [])),
    )


def _first_metadata(
    values: dict[str, list[tuple[str | None, str | None]]], name: str
) -> str | None:
    """Return the first Dublin Core value for ``name``, or ``None`` if it is empty."""
    entries = values.get(name)
    return entries[0][0] if entries and entries[0][0] else None


def _identifier(
    package: etree._Element, identifiers: list[tuple[str | None, str | None]]
) -> str | None:
    """Return the ``dc:identifier`` the package's ``unique-identifier`` names.

    The designation is the whole point of the attribute: a book commonly carries
    several identifiers -- an ISBN, a UUID, a vendor's own -- and the package
    says which one *is* the publication. Position among them says nothing, so
    neither the first nor the last will do.

    A publication that designates none, or designates one it does not carry,
    still has an identity worth publishing, so the first identifier stands in.
    What it must never be is invented: a manifest whose identifier changed
    between two requests for the same file would make every reader's stored
    state name a different book each time it looked.
    """
    unique_id = package.get("unique-identifier")
    designated = next(
        (value for value, element_id in identifiers if element_id == unique_id and value), None
    )
    if designated is not None:
        return designated
    return identifiers[0][0] if identifiers and identifiers[0][0] else None


def _default_layout(package: etree._Element) -> PublicationLayout | None:
    """Read the publication-wide ``rendition:layout`` from the package metadata."""
    for meta in package.iterfind(f"{{{_OPF_NS}}}metadata/{{{_OPF_NS}}}meta"):
        if meta.get("property") == "rendition:layout":
            return _LAYOUT_BY_RENDITION_VALUE.get((meta.text or "").strip())
    return None


def _layout_overrides(package: etree._Element) -> dict[str, PublicationLayout]:
    """Read per-spine-item layout properties, keyed by the manifest id they name."""
    overrides: dict[str, PublicationLayout] = {}
    for itemref in package.iterfind(f"{{{_OPF_NS}}}spine/{{{_OPF_NS}}}itemref"):
        idref = itemref.get("idref")
        if not idref:
            continue
        for prop in (itemref.get("properties") or "").split():
            layout = _LAYOUT_BY_ITEMREF_PROPERTY.get(prop)
            if layout is not None:
                overrides[idref] = layout
    return overrides


def _container_href(opf_dir: str, file_path: str) -> str | None:
    """Encode a decoded, OPF-relative file path as a container-root href.

    The argument is the file's real name, already decoded. Encoding it exactly
    once is what makes the result byte-identical to the ``href`` a derived
    Locator carries for the same file (ADR-0004 §2) -- including for a file
    whose name genuinely contains a percent sign, where decoding a second time
    would name a different file or none at all.

    Returns:
        The percent-encoded container-root path, or ``None`` if the path is
        absolute or climbs out of the container. Such a path names something
        the publication does not contain, and served under the manifest's own
        URL it would resolve to a different endpoint entirely.
    """
    if file_path.startswith("/"):
        return None
    resolved = posixpath.normpath(posixpath.join(opf_dir, file_path))
    if resolved == ".." or resolved.startswith("../"):
        return None
    return quote(resolved, safe="/")


def _document_href(opf_dir: str, href: str) -> str | None:
    """Resolve a navigation link's href, which is kept exactly as written.

    Unlike a manifest file name, this arrives still encoded, so it is decoded
    once here and re-encoded by :func:`_container_href`. The escape check runs
    on the decoded path, so ``..%2F..%2Fx`` is rejected along with ``../../x``.
    """
    path, _, fragment = href.partition("#")
    resolved = _container_href(opf_dir, unquote(path))
    if resolved is None:
        return None
    return f"{resolved}#{quote(unquote(fragment), safe='')}" if fragment else resolved


def _read_navigation(archive: zipfile.ZipFile, package: _PackageDocument) -> tuple[_NavPoint, ...]:
    """Read the publication's table of contents, from the nav document or the NCX.

    EPUB 3 states it in a navigation document and EPUB 2 in an NCX; a
    publication carrying both is read from the nav document, which is the one
    its own version defines. Either way this is one member, and the only member
    of the publication's content that resolving its structure reads.

    A table of contents that cannot be read costs the table of contents and not
    the book: the reading order is what a reader opens, and a publication whose
    navigation is missing or malformed is still one a reader can page through.
    A member that lies about its size is not merely broken, though, so the
    refusal :func:`_read_structural_document` raises passes straight out --
    degrading past a bomb would mean paying for it first.
    """
    source = _navigation_source(package)
    if source is None:
        return ()

    member = posixpath.join(package.directory, source.file_name)
    try:
        return source.parse(_read_structural_document(archive, member), source.base_path)
    except InvalidEbookError:
        raise
    except Exception as e:
        logger.warning(f"Publication navigation {member!r} could not be read: {e!s}")
        return ()


class _NavigationSource(NamedTuple):
    """The member a publication's table of contents is written in.

    Attributes:
        file_name: The member's path relative to the package document.
        base_path: The directory its links resolve against -- its own, for both
            formats, since a link is written relative to the document that
            writes it and neither format has to sit beside the package document.
        parse: The reader for the format it is written in.
    """

    file_name: str
    base_path: str
    parse: Callable[[bytes, str], tuple[_NavPoint, ...]]


def _navigation_source(package: _PackageDocument) -> _NavigationSource | None:
    """Find the navigation document, or the NCX the spine falls back to."""
    for item in package.items:
        if item.media_type == _XHTML_MEDIA_TYPE and _NAV_PROPERTY in item.properties:
            return _NavigationSource(item.file_name, posixpath.dirname(item.file_name), _parse_nav)

    for item in package.items:
        if package.ncx_id and item.item_id == package.ncx_id:
            return _NavigationSource(item.file_name, posixpath.dirname(item.file_name), _parse_ncx)

    return None


def _parse_nav(document: bytes, base_path: str) -> tuple[_NavPoint, ...]:
    """Read an EPUB 3 navigation document's ``toc`` nav into nav points.

    Parsed as HTML rather than as XML because that is what a navigation document
    is served and rendered as, and a book whose nav is not well-formed XML still
    navigates in a browser.
    """
    root = etree.fromstring(document, etree.HTMLParser(encoding="utf-8"))
    navs = cast(list[etree._Element], root.xpath("//nav[@*='toc']"))
    if not navs:
        logger.warning("Navigation document states no table of contents")
        return ()
    ordered_list = navs[0].find("ol")
    return _nav_points(ordered_list, base_path) if ordered_list is not None else ()


def _nav_points(ordered_list: etree._Element, base_path: str) -> tuple[_NavPoint, ...]:
    """Walk one ``<ol>`` of a navigation document, and the lists nested in it.

    An entry with a nested list is titled by its first child whatever that is --
    a link, or the ``<span>`` a heading that links nowhere is written as. An
    entry that is neither a link nor a heading over other entries names nothing
    and is left out.
    """
    points: list[_NavPoint] = []

    for item in ordered_list.findall("li"):
        sublist = item.find("ol")
        link = item.find("a")
        href = link.get("href") if link is not None else None
        if sublist is not None:
            title = _text_content(item[0]) if len(item) else ""
            points.append(
                _NavPoint(title, _nav_href(base_path, href), _nav_points(sublist, base_path))
            )
        elif link is not None and href:
            points.append(_NavPoint(_text_content(link), _nav_href(base_path, href), ()))

    return tuple(points)


def _nav_href(base_path: str, href: str | None) -> str:
    """Resolve a navigation link against the navigation document's own directory.

    The result stays percent-encoded as the document wrote it;
    :func:`_document_href` decodes it once, later and exactly once.
    """
    return posixpath.normpath(posixpath.join(base_path, href)) if href else ""


def _text_content(element: etree._Element) -> str:
    """All the text under an element, as an HTML renderer would show it."""
    return "".join(cast(Iterable[str], element.itertext()))


def _parse_ncx(document: bytes, base_path: str) -> tuple[_NavPoint, ...]:
    """Read an EPUB 2 NCX's ``navMap`` into nav points.

    An NCX ``content`` source is relative to the NCX, which is a manifest item
    like any other and need not sit beside the package document. Resolving one
    anywhere but the NCX's own directory names a file the publication does not
    hold, so a book whose NCX lives in a subdirectory would have a table of
    contents pointing everywhere except at its own reading order.
    """
    nav_map = etree.fromstring(document).find(f"{{{_NCX_NS}}}navMap")
    return _ncx_points(nav_map, base_path) if nav_map is not None else ()


def _ncx_points(parent: etree._Element, base_path: str) -> tuple[_NavPoint, ...]:
    """Walk one NCX element's ``navPoint`` children, and the points nested in them."""
    points: list[_NavPoint] = []

    for point in parent.iterfind(f"{{{_NCX_NS}}}navPoint"):
        label = point.find(f"{{{_NCX_NS}}}navLabel/{{{_NCX_NS}}}text")
        content = point.find(f"{{{_NCX_NS}}}content")
        points.append(
            _NavPoint(
                title=(label.text or "") if label is not None else "",
                href=_nav_href(base_path, content.get("src") if content is not None else None),
                children=_ncx_points(point, base_path),
            )
        )

    return tuple(points)


def _resources(
    items: Iterable[_ManifestItem],
    opf_dir: str,
    layouts: dict[str, PublicationLayout | None],
) -> tuple[PublicationResource, ...]:
    """Render manifest items as publication resources, dropping any that escape.

    A single item pointing outside the container costs that item and not the
    whole book -- a stray image is worth degrading over, and a spine emptied
    this way is caught by the reading-order check in
    :meth:`EpubParserService.parse_publication`.
    """
    resources: list[PublicationResource] = []

    for item in items:
        href = _container_href(opf_dir, item.file_name)
        if href is None:
            logger.warning(
                f"Dropped manifest item pointing outside the publication: {item.item_id!r}"
            )
            continue
        resources.append(
            PublicationResource(
                href=href,
                media_type=item.media_type,
                layout=layouts.get(item.item_id),
            )
        )

    return tuple(resources)


def _toc_entries(points: Iterable[_NavPoint], opf_dir: str) -> tuple[TocEntry, ...]:
    """Render nav points as nested :class:`TocEntry` values.

    Unlike :func:`_extract_toc_hierarchy`, which flattens for chapter storage,
    this keeps the nesting a manifest's ``toc`` renders and keeps the href rather
    than resolving it to an xpointer.
    """
    return tuple(
        TocEntry(
            title=point.title,
            href=_entry_href(point.href, opf_dir),
            children=_toc_entries(point.children, opf_dir),
        )
        for point in points
    )


def _entry_href(href: str, opf_dir: str) -> str | None:
    """Resolve a TOC entry's href, or ``None`` for a heading that links nowhere.

    An href that escapes the container is treated as linking nowhere rather than
    dropping the entry, so a hostile or broken link costs its own line's
    navigation and not the nesting of everything under it.
    """
    if not href:
        return None
    resolved = _document_href(opf_dir, href)
    if resolved is None:
        logger.warning(f"Dropped TOC href pointing outside the publication: {href!r}")
    return resolved


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
    def parse_publication(self, epub_content: bytes) -> ParsedPublication:
        """Resolve an EPUB into its reading order, resources, TOC and metadata.

        Unlike :meth:`parse_toc`, a failure here is raised rather than swallowed:
        a manifest with an empty reading order is not a degraded answer, it is a
        book the reader cannot open.

        Args:
            epub_content: EPUB file content as bytes.

        Returns:
            The publication in Readium's terms, hrefs relative to the container
            root and percent-encoded.

        Raises:
            InvalidEbookError: If the bytes are not a readable EPUB, its package
                document is missing or unparseable, or its spine names nothing
                the publication contains.
        """
        package, navigation = _read_publication(epub_content)

        items_by_id = {item.item_id: item for item in package.items}
        spine_ids = [idref for idref in package.spine if idref in items_by_id]
        if dangling := len(package.spine) - len(spine_ids):
            logger.warning(f"Spine names {dangling} item(s) missing from the manifest")

        reading_order = _resources(
            (items_by_id[idref] for idref in spine_ids),
            package.directory,
            {
                idref: package.layout_by_idref.get(idref, package.default_layout)
                for idref in spine_ids
            },
        )
        if not reading_order:
            raise InvalidEbookError("has no readable spine items", "epub")

        in_spine = set(spine_ids)
        resources = _resources(
            (item for item in package.items if item.item_id not in in_spine),
            package.directory,
            {},
        )

        logger.info(
            f"Parsed publication: {len(reading_order)} reading-order items, "
            f"{len(resources)} resources"
        )
        return ParsedPublication(
            metadata=package.metadata,
            reading_order=reading_order,
            resources=resources,
            toc=_toc_entries(navigation, package.directory),
        )

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
