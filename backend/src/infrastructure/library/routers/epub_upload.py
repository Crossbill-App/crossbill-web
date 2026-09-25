"""Reading an uploaded EPUB, shared by every route that accepts one."""

from fastapi import UploadFile

from src.domain.common.exceptions import ValidationError

MAX_EBOOK_SIZE = 50 * 1024 * 1024
_EPUB_CONTENT_TYPES = {"application/epub+zip", "application/epub"}


def read_epub_upload(upload: UploadFile) -> bytes:
    """Read an uploaded EPUB, rejecting anything that is not one or is too large."""
    # Browsers send an EPUB under all sorts of types, so an .epub name is accepted with
    # any of them; the structure validation that follows is what really decides.
    named_epub = (upload.filename or "").lower().endswith(".epub")
    if upload.content_type not in _EPUB_CONTENT_TYPES and not named_epub:
        raise ValidationError("Only EPUB files are allowed")

    content = upload.file.read(MAX_EBOOK_SIZE + 1)
    if len(content) > MAX_EBOOK_SIZE:
        raise ValidationError(f"File too large (max {MAX_EBOOK_SIZE // (1024 * 1024)}MB)")
    return content
