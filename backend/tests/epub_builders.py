"""Hand-built EPUBs, for the shapes no fixture on disk has.

Shared by the parser's unit tests and the Readium endpoints' API tests, which
need the same broken and hostile publications from either side.
"""

import zipfile
from collections.abc import Mapping
from io import BytesIO

DEFAULT_IDENTIFIERS = '<dc:identifier id="bookid">urn:uuid:hand-built</dc:identifier>'
DOCUMENT = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page</title></head>'
    b"<body><p>Hi there.</p></body></html>"
)

NAV_ITEM = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'


def container_xml(rootfile: str = '<rootfile full-path="content.opf"/>') -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        f"<rootfiles>{rootfile}</rootfiles></container>"
    )


def nav_document(
    list_items: str, attributes: str = 'epub:type="toc"', preceded_by: str = ""
) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
        "<head><title>Contents</title></head>"
        f"<body>{preceded_by}<nav {attributes}><ol>{list_items}</ol></nav></body></html>"
    )


def build_epub(
    manifest_items: str,
    spine: str,
    files: tuple[str, ...] = (),
    unique_identifier: str = "bookid",
    identifiers: str = DEFAULT_IDENTIFIERS,
    extra_metadata: str = "",
    opf_name: str = "content.opf",
    container: str | None = None,
    spine_toc: str | None = None,
    documents: Mapping[str, str] | None = None,
) -> bytes:
    """Assemble an EPUB by hand, so a broken or hostile one reads as such in the diff.

    What the archive really holds (``files``, and ``documents`` for a member
    whose content matters) is deliberately separate from what the manifest
    promises: a manifest naming a file that is not there is one of the shapes
    under test.
    """
    package = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        f'unique-identifier="{unique_identifier}">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"{identifiers}<dc:title>Hand Built</dc:title><dc:language>en</dc:language>"
        f"{extra_metadata}</metadata>"
        f"<manifest>{manifest_items}</manifest>"
        f"<spine{f' toc="{spine_toc}"' if spine_toc is not None else ''}>{spine}</spine></package>"
    )

    out = BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            container
            if container is not None
            else container_xml(f'<rootfile full-path="{opf_name}"/>'),
        )
        archive.writestr(opf_name, package)
        for name in files:
            archive.writestr(name, DOCUMENT)
        for name, content in (documents or {}).items():
            archive.writestr(name, content)
    return out.getvalue()
