"""Read one member of a zip archive without trusting what it says about its size.

Every EPUB here was uploaded by its owner, so the sizes inside it are claims
rather than facts: a member can declare ten bytes and hold two hundred
megabytes. Both the publication parser and, later, the web reader's resource
endpoint read members of such archives, so the read that does not take the claim
on trust lives here rather than in either of them.
"""

import zipfile
import zlib

from src.domain.library.exceptions import InvalidEbookError


def read_bounded_member(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bytes:
    """Read one member, decompressing no more than it said it would.

    A zip entry declares its uncompressed size, and ``ZipFile.read()`` trims its
    answer to that number -- but only its answer. It decompresses the whole
    member first: on CPython 3.13, a member declaring 10 bytes that really holds
    200 MB returns 10 bytes and allocates 437 MiB doing it.
    ``open(entry).read(n)`` passes ``n`` to the decompressor itself, which stops
    there, and the same member then costs 53 KiB.

    Check the declaration before calling this, against whatever cap applies to
    what you are reading. This bounds the read by the claim; it does not judge
    whether the claim itself is a reasonable one.

    The declaration is a bound and not a check: the answer never exceeds it,
    because ``zipfile`` trims to it, so nothing about the length that comes back
    says whether the member was honest. Its CRC-32 does. Reading to the declared
    end verifies it, and a member holding more than it claimed fails there --
    as does one whose stored bytes are simply corrupt. Either is a broken file
    rather than a server fault, so it is re-raised as one.

    Raises:
        InvalidEbookError: If the member is not readable.
    """
    try:
        with archive.open(entry) as member:
            return member.read(entry.file_size)
    except (OSError, zipfile.BadZipFile, EOFError, zlib.error) as e:
        raise InvalidEbookError(f"resource {entry.filename!r} cannot be read: {e!s}", "epub") from e
