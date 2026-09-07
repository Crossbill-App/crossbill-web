"""Reading one member of a zip archive without letting the archive decide the cost.

An EPUB is a file its owner uploaded, so every declaration in it is a claim
rather than a fact, and ``zipfile`` honours a declaration for the *result* of a
read while ignoring it for the *work*. Both the web reader's resource endpoint
and the publication parser read members of an archive on those terms, so the
read that respects them lives here rather than in either of them.
"""

import zipfile

from src.domain.library.exceptions import InvalidEbookError


def read_bounded_member(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bytes:
    """Read one member without letting it decide how much memory that takes.

    ``ZipFile.read()`` returns no more than the declared size but does not
    *work* within it: measured on CPython 3.13, reading a member that declares
    10 bytes and really inflates to 200 MB returns 10 bytes after allocating
    437 MiB, because the decompressor is handed an unbounded output limit and
    only the result is truncated. ``open(entry).read(n)`` passes ``n`` down as
    that limit, so asking for no more than the declaration bounds the work as
    well as the answer -- the same member then costs 53 KiB.

    Check the declaration itself first -- with
    :func:`~src.infrastructure.web_reader.queries.publication_resource_query.check_member_is_servable`
    for a member being served, or against the parser's own cap for a structural
    document; this trusts the declaration to be one worth reading up to.

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
