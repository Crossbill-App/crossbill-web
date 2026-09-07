"""How much a hostile archive can make the resource endpoint allocate.

The endpoint tests assert what a request answers. This one asserts what reading
a member *costs*, which no status code can show and which is the whole point of
the bound: a member's declared size is a claim the archive makes about itself,
and ``zipfile`` honours it for the result while ignoring it for the work.
"""

import struct
import tracemalloc
import zipfile
from io import BytesIO

from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.web_reader.queries.publication_resource_query import (
    MAX_RESOURCE_BYTES,
    read_bounded_member,
)

BOMB_SIZE = 64 * 1024 * 1024


def archive_with(name: str, body: bytes, declared: int | None = None) -> zipfile.ZipFile:
    """One deflated member, optionally rewritten to declare a size it does not have.

    Both the local header and the central directory are patched, so nothing
    short of decompressing the member can tell how big it really is.
    """
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, body)
    raw = bytearray(out.getvalue())
    if declared is not None:
        for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
            struct.pack_into("<I", raw, raw.find(signature) + offset, declared)
    return zipfile.ZipFile(BytesIO(bytes(raw)))


def peak_bytes_reading(archive: zipfile.ZipFile, name: str) -> tuple[object, int]:
    """Read a member and report what the read peaked at, outcome and all."""
    entry = archive.getinfo(name)
    tracemalloc.start()
    try:
        try:
            outcome: object = read_bounded_member(archive, entry)
        except InvalidEbookError as e:
            outcome = e
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return outcome, peak


def test_reads_an_ordinary_member_whole() -> None:
    """Should return the member's bytes unchanged when nothing is wrong with it."""
    body = b"body{color:red}" * 100

    content, _ = peak_bytes_reading(archive_with("main.css", body), "main.css")

    assert content == body


def test_refuses_a_member_declaring_more_than_the_cap() -> None:
    """Should turn away an honest oversized declaration without opening the member."""
    archive = archive_with("big.css", b"A" * 64, declared=MAX_RESOURCE_BYTES + 1)

    outcome, peak = peak_bytes_reading(archive, "big.css")

    assert isinstance(outcome, InvalidEbookError)
    assert peak < 1024 * 1024, "opened a member it had already decided to refuse"


def test_a_member_that_understates_its_size_is_not_inflated() -> None:
    """Should read no more than the member claims, so a lie costs nothing.

    ``ZipFile.read()`` would truncate the *result* to the declared eight bytes
    while handing the decompressor an unbounded output limit, allocating the
    real size first -- measured at 437 MiB for a 200 MB member declaring ten
    bytes. Reading through ``open(entry).read(declared + 1)`` passes the bound
    down to the decompressor, which is what makes the lie cheap to catch.
    """
    archive = archive_with("bomb.css", b"A" * BOMB_SIZE, declared=8)

    outcome, peak = peak_bytes_reading(archive, "bomb.css")

    # The member fails its CRC-32 once the declared bytes run out, which is a
    # broken publication rather than a server fault.
    assert isinstance(outcome, InvalidEbookError)
    assert peak < BOMB_SIZE // 8, f"inflated the member: {peak / 1024 / 1024:.0f} MiB"


def test_the_bound_is_the_declaration_not_the_cap() -> None:
    """Should not allocate the whole cap to read a small member.

    Reading ``MAX_RESOURCE_BYTES`` at a time would bound the damage but pay the
    ceiling on every request; the declaration is the tighter bound and the one
    that makes an understating bomb cost almost nothing.
    """
    archive = archive_with("bomb.css", b"A" * BOMB_SIZE, declared=8)

    _, peak = peak_bytes_reading(archive, "bomb.css")

    assert peak < MAX_RESOURCE_BYTES // 4


def test_a_member_declaring_exactly_the_cap_is_served() -> None:
    """Should refuse only what is strictly over the cap, pinning the boundary.

    Paired with the test above, this is what separates ``>`` from ``>=`` -- a
    limit that turned away the size it advertises would be a different limit.
    """
    body = b"A" * 64
    archive = archive_with("edge.css", body, declared=MAX_RESOURCE_BYTES)

    content, _ = peak_bytes_reading(archive, "edge.css")

    assert content == body
