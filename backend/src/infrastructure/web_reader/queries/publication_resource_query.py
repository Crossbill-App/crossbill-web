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
from src.application.web_reader.queries.publication_resource import (
    ANY_VERSION,
    PublicationResourceView,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.exceptions import InvalidEbookError
from src.domain.web_reader.exceptions import PublicationResourceNotFoundError
from src.infrastructure.web_reader.queries.stored_epub import StoredEpub, load_stored_epub

# Long enough that two files of one book cannot collide by accident, short
# enough to stay readable in a log line or a browser's network panel.
_VERSION_LENGTH = 32

# The largest single file this will serve out of a publication. EPUB resources
# are documents, styles, fonts and images: a chapter runs to kilobytes and even
# a full-page scan in a fixed-layout book to a few megabytes, so this sits two
# orders of magnitude above anything a real book contains and no legitimate
# publication meets it. Audio and video are not EPUB resources and are not
# planned. The parser's own cap is on the archive's *total* declared size, which
# a single near-2-GiB member passes comfortably, so a per-member limit is what
# stops one file from being the whole budget.
MAX_RESOURCE_BYTES = 16 * 1024 * 1024


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
        self, book_id: BookId, user_id: UserId, path: str, known_versions: frozenset[str]
    ) -> PublicationResourceView | None:
        """Return one file of a user's publication, or ``None`` when they have no such book.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
            InvalidEbookError: If the stored EPUB cannot be parsed, or the file is
                too large to serve.
            PublicationResourceNotFoundError: If the publication lists no such file.
        """
        stored = await load_stored_epub(self.db, self.file_repository, book_id, user_id)
        if stored is None:
            return None
        # Parsing the publication and reading a member are both blocking and
        # both CPU-bound, so they share one hop off the event loop rather than
        # stalling every other request in the process for the duration.
        return await asyncio.to_thread(self._read_member, stored, path, known_versions)

    def _read_member(
        self, stored: StoredEpub, path: str, known_versions: frozenset[str]
    ) -> PublicationResourceView:
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

            version = _version(stored, path)
            # Answered before anything is decompressed. The version is made of
            # what the archive's directory already says, so a reader that
            # already holds this file costs a parse and nothing more -- which is
            # the difference between a cheap conditional request and one that
            # inflates a member in full only to discard it.
            if ANY_VERSION in known_versions or version in known_versions:
                return PublicationResourceView(media_type=media_type, content=None, version=version)
            content = _read_bounded(archive, entry)

        return PublicationResourceView(media_type=media_type, content=content, version=version)


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


def _read_bounded(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bytes:
    """Read one member without letting it decide how much memory that takes.

    Two things are needed, because the declared size is both the only cheap
    signal and a claim the archive makes about itself:

    - **The cap refuses an honest declaration for free.** A member declaring
      more than :data:`MAX_RESOURCE_BYTES` is turned away without opening it.
    - **The bounded read contains a dishonest one.** ``ZipFile.read()`` returns
      no more than the declared size but does not *work* within it: measured on
      CPython 3.13, reading a member that declares 10 bytes and really inflates
      to 200 MB returns 10 bytes after allocating 437 MiB, because the
      decompressor is handed an unbounded output limit and only the result is
      truncated. ``open(entry).read(n)`` passes ``n`` down as the decompressor's
      output limit, so asking for no more than the declaration bounds the work
      as well as the answer -- the same member then costs 53 KiB.

    A member that inflates past what it declared fails its CRC-32, which
    ``zipfile`` raises as ``BadZipFile``; that is a broken publication rather
    than a server fault, so it reads as one.

    Raises:
        InvalidEbookError: If the member is over the cap, or is not readable.
    """
    if entry.file_size > MAX_RESOURCE_BYTES:
        raise InvalidEbookError(
            f"resource {entry.filename!r} declares {entry.file_size} bytes, over the "
            f"{MAX_RESOURCE_BYTES} limit",
            "epub",
        )
    try:
        with archive.open(entry) as member:
            return member.read(entry.file_size + 1)
    except (OSError, zipfile.BadZipFile, EOFError) as e:
        raise InvalidEbookError(f"resource {entry.filename!r} cannot be read: {e!s}", "epub") from e


def _version(stored: StoredEpub, path: str) -> str:
    """Derive a resource's opaque version from the archive it came from and its path.

    An entity tag has to identify the bytes being served, and within one
    publication only two things bear on that: which archive it is, and which
    member of it. So the recipe is a digest of the archive's own bytes, the
    member's path, and the name the book is stored under.

    The archive digest is doing the real work, and the alternatives do not.
    Neither the member's CRC-32 nor its declared size identifies anything: two
    empty files share a CRC, and forging a CRC-32 at a fixed length is
    arithmetic rather than search, so a replaced member can present the same
    path, size and checksum over different content. Nor can the stored file name
    stand in for the archive, because a re-upload deliberately reuses it (see
    ``_upload_epub``) -- there is no cheap field on the book row that reliably
    changes when the bytes behind that name do. Hashing the archive is the one
    signal that always does, and it costs a pass over bytes already in memory,
    against a full EPUB parse this request is paying anyway.

    The stored file name is mixed in as well, so that re-uploading the identical
    EPUB under a fresh name still re-tags. That direction only over-invalidates,
    which is the safe way to be wrong.

    The limit worth stating: this identifies the *archive*, not the member's
    decompressed bytes. Making it the latter would mean decompressing every
    member on every conditional request -- exactly the cost the 304 path exists
    to avoid -- for no gain, since equal archives serve equal members.
    """
    archive_digest = hashlib.sha256(stored.content).hexdigest()
    identity = f"{stored.file_name}\0{archive_digest}\0{path}"
    return hashlib.sha256(identity.encode()).hexdigest()[:_VERSION_LENGTH]
