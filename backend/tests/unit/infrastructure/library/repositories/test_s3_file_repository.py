"""Unit tests for S3FileRepository."""

from unittest.mock import MagicMock

import pytest

from src.infrastructure.library.repositories.s3_file_repository import S3FileRepository


@pytest.fixture
def s3_client() -> MagicMock:
    client = MagicMock()
    # Set up exceptions attribute for NoSuchKey
    client.exceptions = MagicMock()
    client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    return client


@pytest.fixture
def repo(s3_client: MagicMock) -> S3FileRepository:
    return S3FileRepository(s3_client=s3_client, bucket_name="test-bucket")


# ---------------------------------------------------------------------------
# save_epub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_epub_uploads_with_correct_key(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    filename = await repo.save_epub("abc123.epub", b"epub-bytes")

    s3_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="epubs/abc123.epub",
        Body=b"epub-bytes",
    )
    assert filename == "abc123.epub"


# ---------------------------------------------------------------------------
# save_cover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_cover_uploads_with_correct_key(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    filename = await repo.save_cover("abc123.jpg", b"image-bytes")

    s3_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="book-covers/abc123.jpg",
        Body=b"image-bytes",
    )
    assert filename == "abc123.jpg"


# ---------------------------------------------------------------------------
# get_epub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_epub_returns_bytes_when_found(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    body_mock = MagicMock()
    body_mock.read.return_value = b"epub-content"
    s3_client.get_object.return_value = {"Body": body_mock}

    result = await repo.get_epub("My_Book_42.epub")

    assert result == b"epub-content"
    s3_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="epubs/My_Book_42.epub")


@pytest.mark.asyncio
async def test_get_epub_returns_none_when_not_found(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    s3_client.get_object.side_effect = s3_client.exceptions.NoSuchKey("not found")

    result = await repo.get_epub("Missing_42.epub")

    assert result is None


# ---------------------------------------------------------------------------
# get_cover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cover_returns_bytes_when_found(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    body_mock = MagicMock()
    body_mock.read.return_value = b"cover-content"
    s3_client.get_object.return_value = {"Body": body_mock}

    result = await repo.get_cover("42.jpg")

    assert result == b"cover-content"


@pytest.mark.asyncio
async def test_get_cover_returns_none_when_not_found(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    s3_client.get_object.side_effect = s3_client.exceptions.NoSuchKey("not found")

    result = await repo.get_cover("42.jpg")

    assert result is None


# ---------------------------------------------------------------------------
# delete_epub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_epub_returns_true_when_deleted(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    result = await repo.delete_epub("My_Book_42.epub")

    assert result is True
    s3_client.delete_object.assert_called_once_with(
        Bucket="test-bucket", Key="epubs/My_Book_42.epub"
    )


@pytest.mark.asyncio
async def test_delete_epub_returns_false_when_not_found(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    s3_client.head_object.side_effect = Exception("not found")

    result = await repo.delete_epub("Missing_42.epub")

    assert result is False
    s3_client.delete_object.assert_not_called()


@pytest.mark.asyncio
async def test_delete_epub_returns_false_on_exception(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    s3_client.delete_object.side_effect = Exception("S3 error")

    result = await repo.delete_epub("My_Book_42.epub")

    assert result is False


# ---------------------------------------------------------------------------
# delete_cover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_cover_returns_true_when_deleted(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    result = await repo.delete_cover("42.jpg")

    assert result is True
    s3_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="book-covers/42.jpg")


@pytest.mark.asyncio
async def test_delete_cover_returns_false_when_not_found(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    s3_client.head_object.side_effect = Exception("not found")

    result = await repo.delete_cover("42.jpg")

    assert result is False


@pytest.mark.asyncio
async def test_delete_cover_returns_false_on_exception(
    repo: S3FileRepository, s3_client: MagicMock
) -> None:
    s3_client.delete_object.side_effect = Exception("S3 error")

    result = await repo.delete_cover("42.jpg")

    assert result is False
