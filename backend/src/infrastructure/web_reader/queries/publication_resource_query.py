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

# The largest single file this will serve out of a publication, derived from the
# 50 MiB `MAX_EBOOK_SIZE` an upload may be.
#
# EPUB 3 carries audio, video, fonts and full-page images as well as documents,
# so "a chapter is small" is no guide at all. What does bound a member is the
# upload: every one of those formats is already compressed and stores at a ratio
# near one, so a media member cannot be much larger than the archive that
# carried it. Sitting above the upload cap therefore admits any member that
# could have arrived as itself -- a 32 MiB comic page included -- while still
# bounding what one request may hold.
#
# Only a member relying on real compression could exceed this, and that means
# text: no publication has a 64 MiB XHTML document. The parser's own cap is on
# the archive's *total* declared size, which one near-2-GiB member passes
# comfortably, so a per-member limit is what stops one file being the whole
# budget.
MAX_RESOURCE_BYTES = 64 * 1024 * 1024

# How much larger than its contents a compressed stream may plausibly be.
# Deflate cannot meaningfully expand data: incompressible input falls back to
# stored blocks, costing five bytes per 64 KiB block plus a small header. The
# allowance is far looser than that -- a sixteenth, plus 256 bytes so tiny
# members are not judged on rounding -- because its job is to catch a stream
# orders of magnitude too big for what it claims to hold, not to police
# encoders.
_COMPRESSED_SLACK_DIVISOR = 16
_COMPRESSED_SLACK_BYTES = 256


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

            # Whether this member may be served at all is settled first: a
            # precondition narrows a request that would otherwise succeed
            # (RFC 9110 §13.2), so it must not turn a refusal into "your copy is
            # current" and leave a reader trusting a file it can never fetch.
            # Both this and the version come from the archive's directory, so
            # neither costs a decompression.
            check_member_is_servable(entry)

            version = _version(stored, path)
            # Answered before anything is decompressed, which is the difference
            # between a cheap conditional request and one that inflates a member
            # in full only to discard it.
            if ANY_VERSION in known_versions or version in known_versions:
                return PublicationResourceView(media_type=media_type, content=None, version=version)
            content = read_bounded_member(archive, entry)

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


def check_member_is_servable(entry: zipfile.ZipInfo) -> None:
    """Decide from the central directory alone whether a member may be served.

    Both questions are answered without decompressing anything, which is what
    lets this run before a conditional request is considered -- a precondition
    narrows a request that would otherwise succeed and must not rescue one that
    would not.

    The **cap** turns away an honest declaration over
    :data:`MAX_RESOURCE_BYTES`.

    The **plausibility check** turns away a dishonest one. A member that really
    inflates past what it declared normally fails its CRC-32, but that check is
    forgeable: a crafted member whose stored checksum equals the CRC of its own
    truncated prefix passes it, and would then be served silently short. The
    compressed size is the tell. Deflate cannot meaningfully expand data, so a
    stream far larger than the declaration could compress to is lying about one
    of the two, and a member declaring eight bytes cannot honestly carry 200 KiB.

    Residual risk, accepted knowingly: a member that overstates by only a little
    -- within the slack -- still slips through with a forged prefix CRC, and is
    served truncated. What remains is an integrity fault confined to one file of
    a book, in an archive its own owner uploaded and only its owner can read;
    memory stays bounded either way. Closing it completely would mean
    decompressing every member to measure it, which is the cost this whole path
    exists to avoid.

    Raises:
        InvalidEbookError: If the member is over the cap or misdescribes itself.
    """
    if entry.file_size > MAX_RESOURCE_BYTES:
        raise InvalidEbookError(
            f"resource {entry.filename!r} declares {entry.file_size} bytes, over the "
            f"{MAX_RESOURCE_BYTES} limit",
            "epub",
        )
    plausible = (
        entry.file_size + entry.file_size // _COMPRESSED_SLACK_DIVISOR + _COMPRESSED_SLACK_BYTES
    )
    if entry.compress_size > plausible:
        raise InvalidEbookError(
            f"resource {entry.filename!r} declares {entry.file_size} bytes but carries a "
            f"compressed stream of {entry.compress_size}",
            "epub",
        )


def read_bounded_member(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bytes:
    """Read one member without letting it decide how much memory that takes.

    ``ZipFile.read()`` returns no more than the declared size but does not
    *work* within it: measured on CPython 3.13, reading a member that declares
    10 bytes and really inflates to 200 MB returns 10 bytes after allocating
    437 MiB, because the decompressor is handed an unbounded output limit and
    only the result is truncated. ``open(entry).read(n)`` passes ``n`` down as
    that limit, so asking for no more than the declaration bounds the work as
    well as the answer -- the same member then costs 53 KiB.

    Call :func:`check_member_is_servable` first; this trusts the declaration to
    be one worth reading up to.

    A member that inflates past what it declared fails its CRC-32, which
    ``zipfile`` raises as ``BadZipFile``; that is a broken publication rather
    than a server fault, so it reads as one.

    Raises:
        InvalidEbookError: If the member is not readable.
    """
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
