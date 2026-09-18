"""Tests for reading one zip member, and for what a member that cannot be read does."""

import io
import struct
import zipfile

import pytest

from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.common.zip_members import read_member


def deflated_archive(members: dict[str, bytes]) -> bytes:
    """An archive holding each member, compressed."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return out.getvalue()


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

    The headers are left alone; the deflate stream behind them no longer decodes.
    """
    with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
        entry = archive.getinfo(name)
    content = bytearray(archive_content)
    name_length, extra_length = struct.unpack_from("<HH", content, entry.header_offset + 26)
    payload = entry.header_offset + 30 + name_length + extra_length
    content[payload + 2] ^= 0xFF
    return bytes(content)


def read_named_member(archive_content: bytes, name: str) -> bytes:
    """Read one named member of an archive held in memory."""
    with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
        return read_member(archive, archive.getinfo(name))


class TestAMemberIsReadBackOrRefused:
    """What an ordinary read returns, and what a member that cannot be read does."""

    def test_an_honest_member_reads_back_whole(self) -> None:
        """Should return exactly the bytes the member was written from."""
        body = b"<html><body><p>Hi there.</p></body></html>" * 100

        assert read_named_member(deflated_archive({"chapter.xhtml": body}), "chapter.xhtml") == body

    def test_a_member_whose_stream_is_cut_short_is_a_broken_publication(self) -> None:
        """Should raise InvalidEbookError rather than let a truncated stream surface."""
        content = with_severed_stream(
            deflated_archive({"chapter.xhtml": b"hello world " * 500}), kept_bytes=12
        )

        with pytest.raises(InvalidEbookError):
            read_named_member(content, "chapter.xhtml")

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
            read_named_member(content, "chapter.xhtml")
