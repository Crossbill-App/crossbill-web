"""Query adapter serving one file out of a book's stored EPUB.

The publication is parsed per request, exactly as the manifest endpoint parses
it, because the parse is what says which files the publication *has* and what
each one is. Holding the parse in a per-book cache is deliberately deferred to
the measurement in #745 (ADR-0004 §4); until then the two endpoints pay the same
cost in the same way rather than one of them growing a private shortcut.
"""

import asyncio
import hashlib
import zipfile
from io import BytesIO
from urllib.parse import unquote

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.publications import ParsedPublication
from src.application.web_reader.queries.publication_resource import PublicationResourceView
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.web_reader.exceptions import PublicationResourceNotFoundError
from src.infrastructure.web_reader.queries.stored_epub import StoredEpub, load_stored_epub

# Long enough that two files of one book cannot collide by accident, short
# enough to stay readable in a log line or a browser's network panel.
_VERSION_LENGTH = 32


class PublicationResourceQuery:
    """Serves one file of a book's publication, byte-for-byte as the EPUB holds it."""

    def __init__(
        self,
        db: AsyncSession,
        file_repository: FileRepositoryProtocol,
        publication_parser: PublicationParserProtocol,
    ) -> None:
        self.db = db
        self.file_repository = file_repository
        self.publication_parser = publication_parser

    async def get_publication_resource(
        self, book_id: BookId, user_id: UserId, path: str
    ) -> PublicationResourceView | None:
        """Return one file of a user's publication, or ``None`` when they have no such book.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
            InvalidEbookError: If the stored EPUB cannot be parsed.
            PublicationResourceNotFoundError: If the publication lists no such file.
        """
        stored = await load_stored_epub(self.db, self.file_repository, book_id, user_id)
        if stored is None:
            return None
        # Parsing the publication and reading a member are both blocking and
        # both CPU-bound, so they share one hop off the event loop rather than
        # stalling every other request in the process for the duration.
        return await asyncio.to_thread(self._read_member, stored, path)

    def _read_member(self, stored: StoredEpub, path: str) -> PublicationResourceView:
        """Find the requested file in the parsed publication and read it out of the archive."""
        publication = self.publication_parser.parse_publication(stored.content)
        media_type = _media_types_by_member(publication).get(path)
        if media_type is None:
            raise PublicationResourceNotFoundError(path)

        with zipfile.ZipFile(BytesIO(stored.content)) as archive:
            try:
                entry = archive.getinfo(path)
            except KeyError:
                # A backstop, not an expected path: the parser reads every
                # manifest item, so a package document naming a file the
                # container does not hold fails the whole publication before
                # this point. It stands so that any future divergence between
                # what the parser lists and what the archive holds is a 404
                # rather than an unhandled KeyError.
                raise PublicationResourceNotFoundError(path) from None
            content = archive.read(entry)

        return PublicationResourceView(
            media_type=media_type,
            content=content,
            version=_version(stored.file_name, entry.CRC),
        )


def _media_types_by_member(publication: ParsedPublication) -> dict[str, str]:
    """Map each file the publication offers to the media type declared for it.

    Membership in this map is the whole access rule, and it is why no separate
    traversal guard is needed here. The keys come from the reading order and the
    resources -- the two lists the manifest publishes -- so the package
    document, ``META-INF/``, the ``mimetype`` member and anything else the
    archive happens to carry are simply absent, as is any path the parser
    already dropped for climbing out of the container. A request naming one of
    those, absolute or relative, finds nothing and is a 404 rather than a served
    file.

    The manifest's hrefs are percent-encoded container-root paths, so decoding
    one exactly once gives back the archive member's own name -- which is also
    what the route hands us, ASGI having decoded the URL path exactly once. A
    file whose name really does contain a percent sign therefore round-trips:
    ``chapter%20one.xhtml`` is published as ``chapter%2520one.xhtml`` and comes
    back as itself, not as ``chapter one.xhtml``.
    """
    return {
        unquote(resource.href): resource.media_type
        for resource in (*publication.reading_order, *publication.resources)
    }


def _version(file_name: str, crc: int) -> str:
    """Derive a resource's opaque version from the book's file and the member's checksum.

    The archive's own CRC-32 comes from the central directory, so no member is
    decompressed to answer a conditional request that will not need its bytes.
    A CRC is far too weak to be a content address, which is exactly why the
    stored file name is mixed in: within one book two files with the same
    contents are the same resource, and replacing the book's EPUB changes every
    version at once even where a member survived byte-identical.

    Hashing rather than concatenating keeps the storage file name off the wire,
    an entity tag being something the client sees and echoes back.
    """
    return hashlib.sha256(f"{file_name}\0{crc}".encode()).hexdigest()[:_VERSION_LENGTH]
