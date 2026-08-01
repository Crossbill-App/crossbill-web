"""S3-compatible repository for file I/O operations."""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _validate_filename(filename: str) -> None:
    """Validate that a filename does not contain path traversal sequences."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError(f"Invalid filename: {filename}")


class S3FileRepository:
    """Repository for managing book files (EPUB, covers) in S3-compatible storage."""

    def __init__(self, s3_client: Any, bucket_name: str) -> None:  # noqa: ANN401
        self._client = s3_client
        self._bucket = bucket_name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_object(self, key: str) -> bytes | None:
        """Get an object from S3 by exact key. Returns None if not found."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()  # type: ignore[no-any-return]
        except self._client.exceptions.NoSuchKey:
            return None

    def _delete_object(self, key: str) -> bool:
        """Delete an object from S3 by exact key. Returns True if deleted."""
        try:
            # Check if exists first
            self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception:
            return False
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            logger.info(f"Deleted S3 object: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete S3 object {key}: {e!s}")
            return False

    def _object_exists(self, key: str) -> bool:
        """Check if an object exists in S3."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public interface (FileRepositoryProtocol)
    # ------------------------------------------------------------------

    async def save_epub(self, filename: str, content: bytes) -> str:
        """Upload an EPUB file to S3."""
        _validate_filename(filename)
        key = f"epubs/{filename}"
        await asyncio.to_thread(self._client.put_object, Bucket=self._bucket, Key=key, Body=content)
        logger.info(f"Uploaded EPUB to S3: {key}")
        return filename

    async def save_cover(self, filename: str, content: bytes) -> str:
        """Upload a cover image to S3."""
        _validate_filename(filename)
        key = f"book-covers/{filename}"
        await asyncio.to_thread(self._client.put_object, Bucket=self._bucket, Key=key, Body=content)
        logger.info(f"Uploaded cover to S3: {key}")
        return filename

    async def delete_epub(self, filename: str | None) -> bool:
        """
        Delete an EPUB file from S3 by filename.

        Args:
            filename: Name of the file to delete, or None

        Returns:
            True if deleted, False if not found, error, or filename is None
        """
        if filename is None:
            return False
        _validate_filename(filename)
        return await asyncio.to_thread(self._delete_object, f"epubs/{filename}")

    async def delete_cover(self, filename: str | None) -> bool:
        """
        Delete a cover image from S3 by filename.

        Args:
            filename: Name of the file to delete, or None

        Returns:
            True if deleted, False if not found, error, or filename is None
        """
        if filename is None:
            return False
        _validate_filename(filename)
        return await asyncio.to_thread(self._delete_object, f"book-covers/{filename}")

    async def get_epub(self, filename: str | None) -> bytes | None:
        """
        Retrieve EPUB file content from S3 by filename.

        Args:
            filename: Name of the file to retrieve, or None

        Returns:
            EPUB bytes or None if not found or filename is None
        """
        if filename is None:
            return None
        _validate_filename(filename)
        return await asyncio.to_thread(self._get_object, f"epubs/{filename}")

    async def get_cover(self, filename: str | None) -> bytes | None:
        """
        Retrieve cover image content from S3 by filename.

        Args:
            filename: Name of the file to retrieve, or None

        Returns:
            Cover image bytes or None if not found or filename is None
        """
        if filename is None:
            return None
        _validate_filename(filename)
        return await asyncio.to_thread(self._get_object, f"book-covers/{filename}")
