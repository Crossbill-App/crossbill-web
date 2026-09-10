"""Tests for reading one zip member on terms the archive does not get to set."""

import io
import struct
import tracemalloc
import zipfile

import pytest

from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.common.zip_members import read_bounded_member


def deflated_archive(members: dict[str, bytes]) -> bytes:
    """An archive holding each member's real bytes, compressed and honestly declared."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return out.getvalue()


def with_declared_size(archive_content: bytes, declared: int) -> bytes:
    """Rewrite what the archive's last member claims to decompress to.

    Both the local header and the central directory are rewritten, so nothing
    short of decompressing the member can tell how big it really is.
    """
    content = bytearray(archive_content)
    for signature, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        struct.pack_into("<I", content, content.rfind(signature) + offset, declared)
    return bytes(content)


def with_severed_stream(archive_content: bytes, kept_bytes: int) -> bytes:
    """Cut the archive's last member's compressed stream short of its end.

    The headers keep pointing at a member; what they point at is no longer a
    stream that decompresses back to what was written.
    """
    content = bytearray(archive_content)
    for signature, offset in ((b"PK\x03\x04", 18), (b"PK\x01\x02", 20)):
        struct.pack_into("<I", content, content.rfind(signature) + offset, kept_bytes)
    return bytes(content)


def with_corrupt_payload(archive_content: bytes, name: str) -> bytes:
    """Scribble over the start of a member's compressed stream.

    The headers are left alone, so the archive still describes a member of the
    size it really is; the deflate stream behind them no longer decodes.
    """
    with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
        entry = archive.getinfo(name)
    content = bytearray(archive_content)
    name_length, extra_length = struct.unpack_from("<HH", content, entry.header_offset + 26)
    payload = entry.header_offset + 30 + name_length + extra_length
    content[payload + 2] ^= 0xFF
    return bytes(content)


def read_member(archive_content: bytes, name: str) -> bytes:
    """Read one named member of an archive held in memory."""
    with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
        return read_bounded_member(archive, archive.getinfo(name))


class TestAMemberCostsWhatItDeclares:
    """What a member declares has to bound the work, not only the answer.

    An archive is a file its owner uploaded, so its declarations are claims:
    a member is free to declare eight bytes and really inflate to 64 MiB.
    ``ZipFile.read()`` truncates such a member's result to the declaration
    while allocating the whole of it, which turns one read into as much memory
    as the archive cares to ask for.
    """

    BOMB_SIZE = 64 * 1024 * 1024

    @staticmethod
    def _outcome_and_peak(archive_content: bytes, name: str) -> tuple[object, int]:
        """Read a hostile member and report the outcome and what the read peaked at."""
        tracemalloc.start()
        try:
            try:
                outcome: object = read_member(archive_content, name)
            except InvalidEbookError as e:
                outcome = e
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        return outcome, peak

    def test_a_member_that_understates_its_size_is_not_inflated(self) -> None:
        """Should cost what the member declared rather than what it really holds.

        The lie is also refused rather than served as a short answer: the eight
        bytes that come back do not match the CRC-32 of what was compressed, so
        the member reads as broken. That refusal is worth nothing on its own --
        an unbounded read reaches the same CRC-32 check, having allocated the
        whole 64 MiB to get there.
        """
        content = with_declared_size(deflated_archive({"big.css": b"A" * self.BOMB_SIZE}), 8)
        assert len(content) < 1024 * 1024, "the archive itself should be small"

        outcome, peak = self._outcome_and_peak(content, "big.css")

        assert isinstance(outcome, InvalidEbookError)
        assert peak < self.BOMB_SIZE // 8, f"inflated the member: {peak / 1024**2:.0f} MiB"


class TestAMemberIsReadBackOrRefused:
    """What an ordinary read returns, and what a member that cannot be read does."""

    def test_an_honest_member_reads_back_whole(self) -> None:
        """Should return exactly the bytes the member was written from."""
        body = b"<html><body><p>Hi there.</p></body></html>" * 100

        assert read_member(deflated_archive({"chapter.xhtml": body}), "chapter.xhtml") == body

    def test_a_member_whose_stream_is_cut_short_is_a_broken_publication(self) -> None:
        """Should raise InvalidEbookError rather than let a truncated stream surface."""
        content = with_severed_stream(
            deflated_archive({"chapter.xhtml": b"hello world " * 500}), kept_bytes=12
        )

        with pytest.raises(InvalidEbookError):
            read_member(content, "chapter.xhtml")

    def test_a_member_whose_stream_is_gibberish_is_a_broken_publication(self) -> None:
        """Should raise InvalidEbookError rather than a bare zlib error.

        Corrupt compressed bytes fail inside zlib, which raises ``zlib.error``
        -- neither an ``OSError`` nor a ``BadZipFile``. Left uncaught it would
        reach a caller that has no reason to know this archive was ever a zip.
        """
        content = with_corrupt_payload(
            deflated_archive({"chapter.xhtml": b"hello world " * 500}), "chapter.xhtml"
        )

        with pytest.raises(InvalidEbookError):
            read_member(content, "chapter.xhtml")
