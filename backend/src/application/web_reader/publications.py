"""The vocabulary the publication-parser port speaks: what an EPUB looks like to Readium.

A ``ParsedPublication`` is one EPUB expressed the way the `Readium Web Publication
Manifest <https://readium.org/webpub-manifest/>`_ expresses a book -- a reading
order, a bag of supporting resources, a table of contents, and some metadata --
with everything EPUB-specific (the package document, the spine, the NCX or nav
document) already resolved away.

Every value here is read from the file. An ``href`` is a path inside the EPUB
container, relative to the container root and percent-encoded; holding every
href in that one coordinate system is what lets a highlight's derived locator
name a resource the manifest also lists. What says where the publication is
*served* -- the manifest's ``links`` and ``@context`` -- the router adds when it
renders these values as a manifest.
"""

from dataclasses import dataclass
from enum import StrEnum


class PublicationLayout(StrEnum):
    """The Readium ``properties.layout`` of a reading-order item.

    EPUB says this with ``rendition:layout``, either once for the whole
    publication or per spine item; Readium says it per reading-order item. A
    resource whose layout is left unstated carries no ``layout`` at all rather
    than a guessed default, so a reader applies its own.
    """

    REFLOWABLE = "reflowable"
    FIXED = "fixed"


@dataclass(frozen=True)
class PublicationMetadata:
    """What the EPUB's package document -- its ``.opf`` -- says about the book itself.

    Every field is optional because the package document may omit it -- ``title`` included,
    which is invalid EPUB but does occur. Callers that must render a title fall
    back to the one the library holds.

    Attributes:
        title: ``dc:title``.
        author: The first ``dc:creator``.
        language: The first ``dc:language``, a BCP 47 tag.
        identifier: The ``dc:identifier`` named by the package's
            ``unique-identifier``.
    """

    title: str | None
    author: str | None
    language: str | None
    identifier: str | None


@dataclass(frozen=True)
class PublicationResource:
    """One file of the publication: a reading-order document or a supporting asset.

    Attributes:
        href: The file's path inside the EPUB container, relative to the
            container root and percent-encoded.
        media_type: The media type the package document declares for it.
        size: The uncompressed size the archive declares for the member, in
            bytes. A conditional request's ``Content-Length`` and the position
            list are both computed from it.
        layout: The Readium layout, for reading-order items that state one.
            Always ``None`` for supporting resources, which have no layout.
    """

    href: str
    media_type: str
    size: int
    layout: PublicationLayout | None = None


@dataclass(frozen=True)
class TocEntry:
    """One line of the table of contents, with the lines nested under it.

    Attributes:
        title: The entry's text.
        href: Where it points, in the same form as
            :attr:`PublicationResource.href` but possibly carrying a fragment.
            ``None`` for a heading that links nowhere.
        children: The entries nested below this one, in reading order.
    """

    title: str
    href: str | None
    children: tuple["TocEntry", ...] = ()


@dataclass(frozen=True)
class ParsedPublication:
    """One EPUB, resolved into the shape a Web Publication Manifest renders.

    Attributes:
        metadata: What the package document says about the book.
        reading_order: The spine, in order -- the documents a reader pages
            through.
        resources: Every other file the package document lists (styles, images,
            fonts, the navigation document), in package-document order.
        toc: The table of contents, nested.
        content_hash: The sha256 hex digest of the EPUB archive's bytes,
            identifying the exact file the publication was parsed from. It is
            what a resource's ETag is built from.
    """

    metadata: PublicationMetadata
    reading_order: tuple[PublicationResource, ...]
    resources: tuple[PublicationResource, ...]
    toc: tuple[TocEntry, ...]
    content_hash: str
