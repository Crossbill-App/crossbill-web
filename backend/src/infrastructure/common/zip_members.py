"""Read one member of a zip archive, refusing a broken one as a broken book."""

import zipfile
import zlib

from src.domain.library.exceptions import InvalidEbookError


def read_member(archive: zipfile.ZipFile, entry: zipfile.ZipInfo) -> bytes:
    """Read one member whole.

    A corrupt or truncated stream fails inside zlib or the archive reader, and
    either is a broken file rather than a server fault, so it is re-raised as one.

    Raises:
        InvalidEbookError: If the member is not readable.
    """
    try:
        return archive.read(entry)
    except (OSError, zipfile.BadZipFile, EOFError, zlib.error) as e:
        raise InvalidEbookError(f"resource {entry.filename!r} cannot be read: {e!s}", "epub") from e
