"""Repository for file I/O operations."""

import asyncio
import logging

from src.config import BOOK_COVERS_DIR, EPUBS_DIR  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


def _validate_filename(filename: str) -> None:
    """Validate that a filename does not contain path traversal sequences."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError(f"Invalid filename: {filename}")


class FileRepository:
    """Repository for managing book files (EPUB, covers)."""

    async def save_epub(self, filename: str, content: bytes) -> str:
        """Save an EPUB file to disk."""
        _validate_filename(filename)
        await asyncio.to_thread(lambda: EPUBS_DIR.mkdir(parents=True, exist_ok=True))
        file_path = EPUBS_DIR / filename
        await asyncio.to_thread(file_path.write_bytes, content)
        logger.info(f"Saved EPUB file: {file_path}")
        return file_path.name

    async def save_cover(self, filename: str, content: bytes) -> str:
        """Save a cover image to disk."""
        _validate_filename(filename)
        await asyncio.to_thread(lambda: BOOK_COVERS_DIR.mkdir(parents=True, exist_ok=True))
        file_path = BOOK_COVERS_DIR / filename
        await asyncio.to_thread(file_path.write_bytes, content)
        logger.info(f"Saved cover file: {file_path}")
        return file_path.name

    async def delete_epub(self, filename: str | None) -> bool:
        """
        Delete an EPUB file by filename.

        Args:
            filename: Name of the file to delete, or None

        Returns:
            True if file was deleted, False if not found or filename is None
        """
        if filename is None:
            return False
        _validate_filename(filename)
        file_path = EPUBS_DIR / filename
        if not await asyncio.to_thread(file_path.exists):
            logger.info(f"No EPUB file found: {file_path}")
            return False

        try:
            await asyncio.to_thread(file_path.unlink)
            logger.info(f"Deleted EPUB file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete EPUB file {file_path}: {e!s}")
            return False

    async def delete_cover(self, filename: str | None) -> bool:
        """
        Delete a cover image by filename.

        Args:
            filename: Name of the file to delete, or None

        Returns:
            True if file was deleted, False if not found or filename is None
        """
        if filename is None:
            return False
        _validate_filename(filename)
        file_path = BOOK_COVERS_DIR / filename
        if not await asyncio.to_thread(file_path.exists):
            logger.info(f"No cover file found: {file_path}")
            return False

        try:
            await asyncio.to_thread(file_path.unlink)
            logger.info(f"Deleted cover file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete cover file {file_path}: {e!s}")
            return False

    async def get_epub(self, filename: str | None) -> bytes | None:
        """
        Get EPUB file content by filename.

        Args:
            filename: Name of the file to read

        Returns:
            EPUB file content as bytes, or None if not found
        """
        if filename is None:
            return None
        _validate_filename(filename)
        file_path = EPUBS_DIR / filename
        if not await asyncio.to_thread(file_path.exists):
            return None
        return await asyncio.to_thread(file_path.read_bytes)

    async def get_cover(self, filename: str | None) -> bytes | None:
        """
        Get cover image content by filename.

        Args:
            filename: Name of the file to read

        Returns:
            Cover image content as bytes, or None if not found
        """
        if filename is None:
            return None
        _validate_filename(filename)
        file_path = BOOK_COVERS_DIR / filename
        if not await asyncio.to_thread(file_path.exists):
            return None
        return await asyncio.to_thread(file_path.read_bytes)
