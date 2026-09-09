"""Read an EPUB into the index a Readium Web Publication Manifest is rendered from."""

# pyright: reportPrivateUsage=false

import hashlib
import logging
import mimetypes
import posixpath
import zipfile
from collections.abc import Iterable
from io import BytesIO
from typing import NamedTuple
from urllib.parse import quote, unquote

from lxml import etree

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationMetadata,
    PublicationResource,
)
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.common.zip_members import read_bounded_member

logger = logging.getLogger(__name__)

CONTAINER_PATH = "META-INF/container.xml"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
_OPF_NS = "http://www.idpf.org/2007/opf"
_DC_NS = "http://purl.org/dc/elements/1.1/"

_FALLBACK_MEDIA_TYPE = "application/octet-stream"
# Publishers write this one often enough that every reader corrects it.
_MEDIA_TYPE_CORRECTIONS = {"image/jpg": "image/jpeg"}

# A package document lists one item per archive member, so at a generous 200
# bytes an item even a ten-thousand-file book writes about 2 MB of one.
MAX_STRUCTURAL_DOCUMENT_BYTES = 16 * 1024 * 1024


class _ManifestItem(NamedTuple):
    """One ``<item>`` of the package document's manifest."""

    item_id: str
    file_name: str
    media_type: str


class _PackageDocument(NamedTuple):
    """One parsed OPF: where it sits in the container, and everything an index is made of."""

    directory: str
    metadata: PublicationMetadata
    items: tuple[_ManifestItem, ...]
    spine: tuple[str, ...]


def read_publication(epub_content: bytes) -> ParsedPublication:
    """Resolve an EPUB into its reading order, resources and metadata.

    Raises:
        InvalidEbookError: If the bytes are not a readable EPUB, its package
            document is missing, oversized or unparseable, or its spine names
            nothing the publication contains.
    """
    try:
        with zipfile.ZipFile(BytesIO(epub_content)) as archive:
            package = _read_package_document(archive)
            sizes = {entry.filename: entry.file_size for entry in archive.infolist()}
    except InvalidEbookError:
        raise
    except Exception as e:
        raise InvalidEbookError(f"unreadable package document: {e!s}", "epub") from e

    items_by_id = {item.item_id: item for item in package.items}
    spine_ids = [idref for idref in package.spine if idref in items_by_id]
    reading_order = _resources(
        (items_by_id[idref] for idref in spine_ids), package.directory, sizes
    )
    if not reading_order:
        raise InvalidEbookError("has no readable spine items", "epub")

    in_spine = set(spine_ids)
    resources = _resources(
        (item for item in package.items if item.item_id not in in_spine), package.directory, sizes
    )

    logger.info(
        f"Parsed publication: {len(reading_order)} reading-order items, {len(resources)} resources"
    )
    return ParsedPublication(
        metadata=package.metadata,
        reading_order=reading_order,
        resources=resources,
        toc=(),
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
    return _PackageDocument(
        directory=directory,
        metadata=_metadata(package),
        items=_manifest_items(package),
        spine=tuple(
            idref
            for itemref in _children(package.find(f"{{{_OPF_NS}}}spine"), f"{{{_OPF_NS}}}itemref")
            if (idref := itemref.get("idref"))
        ),
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


def _container_path(opf_dir: str, file_name: str) -> str | None:
    # A path that leaves the container names something the publication does not
    # hold; under the manifest's own URL a leading ``//`` even names another host.
    resolved = posixpath.normpath(posixpath.join(opf_dir, file_name))
    if resolved.startswith(("/", "../")) or resolved == "..":
        return None
    return resolved


def _resources(
    items: Iterable[_ManifestItem], opf_dir: str, sizes: dict[str, int]
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
                href=quote(container_path, safe="/"), media_type=item.media_type, size=size
            )
        )

    return tuple(resources)
