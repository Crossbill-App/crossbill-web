# S3 FileRepository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an S3-compatible `FileRepository` implementation so both app and worker containers can share file storage without shared volumes.

**Architecture:** A new `S3FileRepository` class implements the existing `FileRepositoryProtocol` (bytes-based interface). It uses boto3 to upload/download files to an S3-compatible bucket. The DI container conditionally selects between local `FileRepository` and `S3FileRepository` based on whether S3 env vars are set. For local development, Garage (S3-compatible) runs via docker-compose.

**Tech Stack:** boto3 (S3 SDK), Garage (local S3-compatible dev server), dependency-injector, pydantic-settings

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `pyproject.toml` | Add boto3 dependency |
| Modify | `src/config.py` | Add S3 settings fields |
| Create | `src/infrastructure/library/repositories/s3_file_repository.py` | S3 implementation of FileRepositoryProtocol |
| Create | `tests/unit/infrastructure/library/repositories/test_s3_file_repository.py` | Unit tests for S3FileRepository |
| Modify | `src/containers/shared.py` | Conditional file_repository selection |
| Modify | `backend/.env.example` | Document S3 env vars |
| Modify | `backend/docker-compose.yml` | Add Garage service for local dev |
| Modify | `docker-compose.yml` (root) | Add S3 env vars to app and worker |

---

## Task 1: Add boto3 Dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add boto3 to dependencies**

In `pyproject.toml`, add to the `dependencies` list:

```
"boto3>=1.38.0,<2.0.0",
```

- [ ] **Step 2: Install**

Run: `uv sync`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add boto3 dependency for S3 storage support"
```

---

## Task 2: Add S3 Settings to Config

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Add S3 fields to Settings class**

In `src/config.py`, add these fields to the `Settings` class, after the AI configuration section (after line ~80):

```python
    # S3-compatible storage (optional — if set, files are stored in S3 instead of local disk)
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None
    S3_REGION: str = "us-east-1"
```

Add a computed field after the `ai_enabled` computed field:

```python
    @computed_field  # type: ignore[prop-decorator]
    @property
    def s3_enabled(self) -> bool:
        """Whether S3 storage is enabled."""
        return (
            self.S3_ENDPOINT_URL is not None
            and self.S3_ACCESS_KEY_ID is not None
            and self.S3_SECRET_ACCESS_KEY is not None
            and self.S3_BUCKET_NAME is not None
        )
```

- [ ] **Step 2: Commit**

```bash
git add src/config.py
git commit -m "feat: add S3 configuration settings"
```

---

## Task 3: Implement S3FileRepository

**Files:**
- Create: `src/infrastructure/library/repositories/s3_file_repository.py`
- Test: `tests/unit/infrastructure/library/repositories/test_s3_file_repository.py`

- [ ] **Step 1: Write unit tests**

Create `tests/unit/infrastructure/library/repositories/test_s3_file_repository.py`:

```python
"""Unit tests for S3FileRepository."""

import re
from unittest.mock import MagicMock, patch

import pytest

from src.domain.common.value_objects.ids import BookId
from src.infrastructure.library.repositories.s3_file_repository import S3FileRepository


@pytest.fixture
def mock_s3_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_s3_client: MagicMock) -> S3FileRepository:
    return S3FileRepository(
        s3_client=mock_s3_client,
        bucket_name="test-bucket",
    )


@pytest.fixture
def book_id() -> BookId:
    return BookId(42)


class TestSaveEpub:
    async def test_uploads_to_s3_and_returns_filename(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        content = b"fake epub"
        result = await repo.save_epub(book_id, content, "My Book Title")

        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"].startswith("epubs/")
        assert call_kwargs["Key"].endswith("_42.epub")
        assert call_kwargs["Body"] == b"fake epub"
        assert result == call_kwargs["Key"].split("/", 1)[1]

    async def test_deletes_existing_before_save(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        # Set up list_objects_v2 to return an existing file
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "epubs/OldTitle_42.epub"}]
        }

        await repo.save_epub(book_id, b"new content", "New Title")

        # Should have deleted the old file
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="epubs/OldTitle_42.epub"
        )
        # And uploaded the new one
        mock_s3_client.put_object.assert_called_once()

    async def test_sanitizes_title_in_key(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        await repo.save_epub(book_id, b"content", 'My "Special" Book: A Story')

        call_kwargs = mock_s3_client.put_object.call_args[1]
        key = call_kwargs["Key"]
        # Should not contain special characters
        filename = key.split("/", 1)[1]
        assert '"' not in filename
        assert ":" not in filename


class TestSavePdf:
    async def test_uploads_to_s3_and_returns_filename(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        result = await repo.save_pdf(book_id, b"fake pdf", "My PDF")

        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Key"].startswith("pdfs/")
        assert call_kwargs["Key"].endswith("_42.pdf")
        assert result == call_kwargs["Key"].split("/", 1)[1]


class TestSaveCover:
    async def test_uploads_to_s3_and_returns_filename(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        result = await repo.save_cover(book_id, b"fake image")

        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Key"] == "book-covers/42.jpg"
        assert result == "42.jpg"


class TestGetEpub:
    async def test_returns_bytes_when_found(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "epubs/MyBook_42.epub"}]
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b"epub bytes"))
        }

        result = await repo.get_epub(book_id)

        assert result == b"epub bytes"
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="epubs/MyBook_42.epub"
        )

    async def test_returns_none_when_not_found(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        mock_s3_client.list_objects_v2.return_value = {}

        result = await repo.get_epub(book_id)

        assert result is None


class TestGetCover:
    async def test_returns_bytes_when_found(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "book-covers/42.jpg"}]
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b"cover bytes"))
        }

        result = await repo.get_cover(book_id)

        assert result == b"cover bytes"


class TestDeleteEpub:
    async def test_deletes_and_returns_true(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "epubs/MyBook_42.epub"}]
        }

        result = await repo.delete_epub(book_id)

        assert result is True
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="epubs/MyBook_42.epub"
        )

    async def test_returns_false_when_not_found(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        mock_s3_client.list_objects_v2.return_value = {}

        result = await repo.delete_epub(book_id)

        assert result is False


class TestHasCover:
    async def test_returns_true_when_exists(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "book-covers/42.jpg"}]
        }

        result = await repo.has_cover(book_id)

        assert result is True

    async def test_returns_false_when_not_exists(
        self, repo: S3FileRepository, mock_s3_client: MagicMock, book_id: BookId
    ) -> None:
        mock_s3_client.list_objects_v2.return_value = {}

        result = await repo.has_cover(book_id)

        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pytest tests/unit/infrastructure/library/repositories/test_s3_file_repository.py -v`
Expected: FAIL with `ModuleNotFoundError` (s3_file_repository doesn't exist yet)

- [ ] **Step 3: Implement S3FileRepository**

Create `src/infrastructure/library/repositories/s3_file_repository.py`:

```python
"""S3-compatible file repository implementation."""

import asyncio
import logging
import re
from typing import Any

from src.domain.common.value_objects.ids import BookId

logger = logging.getLogger(__name__)

# S3 key prefixes (mirror local directory structure)
EPUBS_PREFIX = "epubs/"
PDFS_PREFIX = "pdfs/"
COVERS_PREFIX = "book-covers/"


def _sanitize_title(text: str) -> str:
    """Sanitize text for use in S3 key names."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "", text)
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = sanitized.strip("_.")
    max_length = 100
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized


class S3FileRepository:
    """Repository for managing book files in S3-compatible storage."""

    def __init__(self, s3_client: Any, bucket_name: str) -> None:  # noqa: ANN401
        self._s3 = s3_client
        self._bucket = bucket_name

    def _find_keys(self, prefix: str, pattern: str) -> list[str]:
        """Find S3 keys matching a prefix and glob-like pattern."""
        response = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
        contents = response.get("Contents", [])
        import fnmatch

        return [obj["Key"] for obj in contents if fnmatch.fnmatch(obj["Key"], pattern)]

    async def save_epub(self, book_id: BookId, content: bytes, title: str) -> str:
        await self.delete_epub(book_id)
        sanitized_title = _sanitize_title(title)
        filename = f"{sanitized_title}_{book_id.value}.epub"
        key = f"{EPUBS_PREFIX}{filename}"
        await asyncio.to_thread(
            self._s3.put_object, Bucket=self._bucket, Key=key, Body=content
        )
        logger.info("Saved EPUB to S3", extra={"key": key})
        return filename

    async def save_pdf(self, book_id: BookId, content: bytes, title: str) -> str:
        sanitized_title = _sanitize_title(title)
        filename = f"{sanitized_title}_{book_id.value}.pdf"
        key = f"{PDFS_PREFIX}{filename}"
        await asyncio.to_thread(
            self._s3.put_object, Bucket=self._bucket, Key=key, Body=content
        )
        logger.info("Saved PDF to S3", extra={"key": key})
        return filename

    async def save_cover(self, book_id: BookId, content: bytes) -> str:
        filename = f"{book_id.value}.jpg"
        key = f"{COVERS_PREFIX}{filename}"
        await asyncio.to_thread(
            self._s3.put_object, Bucket=self._bucket, Key=key, Body=content
        )
        logger.info("Saved cover to S3", extra={"key": key})
        return filename

    async def delete_epub(self, book_id: BookId) -> bool:
        return await self._delete_by_pattern(
            EPUBS_PREFIX, f"{EPUBS_PREFIX}*_{book_id.value}.epub"
        )

    async def delete_pdf(self, book_id: BookId) -> bool:
        return await self._delete_by_pattern(
            PDFS_PREFIX, f"{PDFS_PREFIX}*_{book_id.value}.pdf"
        )

    async def delete_cover(self, book_id: BookId) -> bool:
        return await self._delete_by_pattern(
            COVERS_PREFIX, f"{COVERS_PREFIX}{book_id.value}.*"
        )

    async def get_epub(self, book_id: BookId) -> bytes | None:
        return await self._get_by_pattern(
            EPUBS_PREFIX, f"{EPUBS_PREFIX}*_{book_id.value}.epub"
        )

    async def get_pdf(self, book_id: BookId) -> bytes | None:
        return await self._get_by_pattern(
            PDFS_PREFIX, f"{PDFS_PREFIX}*_{book_id.value}.pdf"
        )

    async def get_cover(self, book_id: BookId) -> bytes | None:
        return await self._get_by_pattern(
            COVERS_PREFIX, f"{COVERS_PREFIX}{book_id.value}.*"
        )

    async def has_cover(self, book_id: BookId) -> bool:
        keys = await asyncio.to_thread(
            self._find_keys, COVERS_PREFIX, f"{COVERS_PREFIX}{book_id.value}.*"
        )
        return len(keys) > 0

    async def _delete_by_pattern(self, prefix: str, pattern: str) -> bool:
        keys = await asyncio.to_thread(self._find_keys, prefix, pattern)
        if not keys:
            return False
        try:
            await asyncio.to_thread(
                self._s3.delete_object, Bucket=self._bucket, Key=keys[0]
            )
            logger.info("Deleted from S3", extra={"key": keys[0]})
            return True
        except Exception as e:
            logger.error("Failed to delete from S3", extra={"key": keys[0], "error": str(e)})
            return False

    async def _get_by_pattern(self, prefix: str, pattern: str) -> bytes | None:
        keys = await asyncio.to_thread(self._find_keys, prefix, pattern)
        if not keys:
            return None
        response = await asyncio.to_thread(
            self._s3.get_object, Bucket=self._bucket, Key=keys[0]
        )
        return response["Body"].read()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pytest tests/unit/infrastructure/library/repositories/test_s3_file_repository.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run pyright on the new file**

Run: `cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pyright src/infrastructure/library/repositories/s3_file_repository.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/library/repositories/s3_file_repository.py tests/unit/infrastructure/library/repositories/test_s3_file_repository.py
git commit -m "feat: add S3FileRepository implementation with tests"
```

---

## Task 4: Wire Conditional File Repository in DI Container

**Files:**
- Modify: `src/containers/shared.py`

- [ ] **Step 1: Update SharedContainer**

In `src/containers/shared.py`, replace the current `file_repository` line:

```python
    file_repository = providers.Factory(FileRepository)
```

with a conditional factory that checks settings:

```python
    settings = providers.Dependency()

    file_repository = providers.Selector(
        providers.Callable(lambda settings: "s3" if settings.s3_enabled else "local", settings=settings),
        s3=providers.Singleton(
            _create_s3_file_repository,
            settings=settings,
        ),
        local=providers.Factory(FileRepository),
    )
```

Add the necessary imports at the top of the file:

```python
from src.infrastructure.library.repositories.s3_file_repository import S3FileRepository
```

Add this factory function before the `SharedContainer` class:

```python
def _create_s3_file_repository(settings: Any) -> S3FileRepository:  # noqa: ANN401
    """Create an S3FileRepository with a configured boto3 client."""
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    return S3FileRepository(s3_client=client, bucket_name=settings.S3_BUCKET_NAME)
```

Add `from typing import Any` to imports if not already present.

- [ ] **Step 2: Update RootContainer to pass settings**

In `src/containers/root.py`, update the `shared` container wiring to pass settings:

```python
from src.config import get_settings
```

Change:
```python
    shared = providers.Container(SharedContainer, db=db)
```
to:
```python
    settings = providers.Object(get_settings())

    shared = providers.Container(SharedContainer, db=db, settings=settings)
```

- [ ] **Step 3: Run pyright on both files**

Run: `cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pyright src/containers/shared.py src/containers/root.py`
Expected: 0 errors

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pytest`
Expected: All tests pass (existing tests use local file repo since no S3 env vars are set)

- [ ] **Step 5: Commit**

```bash
git add src/containers/shared.py src/containers/root.py
git commit -m "feat: conditionally select S3 or local FileRepository via DI"
```

---

## Task 5: Update Configuration Files

**Files:**
- Modify: `backend/.env.example`
- Modify: `backend/docker-compose.yml` (dev)
- Modify: `docker-compose.yml` (root/production)

- [ ] **Step 1: Add S3 config to .env.example**

Add this section to the end of `backend/.env.example`:

```
# S3-compatible storage (optional)
# When configured, files are stored in S3 instead of local disk.
# This is required for multi-container deployments (e.g., Railway)
# where app and worker containers cannot share a filesystem.
#
# For local development with Garage (run `docker compose up garage`):
# S3_ENDPOINT_URL=http://localhost:3900
# S3_ACCESS_KEY_ID=GKtest01
# S3_SECRET_ACCESS_KEY=testsecretkey0123456789
# S3_BUCKET_NAME=crossbill-files
# S3_REGION=garage
#
# For Railway or AWS S3:
# S3_ENDPOINT_URL=https://your-s3-endpoint.example.com
# S3_ACCESS_KEY_ID=your-access-key
# S3_SECRET_ACCESS_KEY=your-secret-key
# S3_BUCKET_NAME=crossbill-files
# S3_REGION=us-east-1
```

- [ ] **Step 2: Add Garage service to backend/docker-compose.yml**

Add a `garage` service to `backend/docker-compose.yml` (the dev compose file):

```yaml
  garage:
    image: dxflrs/garage:v1.1.0
    container_name: crossbill-garage
    restart: unless-stopped
    ports:
      - "3900:3900"  # S3 API
      - "3902:3902"  # Admin API
    volumes:
      - garage_data:/var/lib/garage/data
      - garage_meta:/var/lib/garage/meta
    environment:
      GARAGE_RPC_SECRET: "0000000000000000000000000000000000000000000000000000"
      GARAGE_RPC_BIND_ADDR: "[::]:3901"
      GARAGE_S3_API_BIND_ADDR: "[::]:3900"
      GARAGE_ADMIN_API_BIND_ADDR: "[::]:3902"
      GARAGE_ADMIN_TOKEN: "admin-token"
      GARAGE_ALLOW_WORLD_READABLE_SECRETS: "true"
      # Single-node setup
      GARAGE_REPLICATION_FACTOR: 1
      GARAGE_DB_ENGINE: "sqlite"
      GARAGE_METADATA_DIR: "/var/lib/garage/meta"
      GARAGE_DATA_DIR: "/var/lib/garage/data"
```

Add to the `volumes` section:
```yaml
  garage_data:
    driver: local
  garage_meta:
    driver: local
```

- [ ] **Step 3: Add S3 env vars to production docker-compose.yml**

In the root `docker-compose.yml`, add S3 env vars to both `app` and `worker` services' environment sections:

```yaml
      S3_ENDPOINT_URL: ${S3_ENDPOINT_URL:-}
      S3_ACCESS_KEY_ID: ${S3_ACCESS_KEY_ID:-}
      S3_SECRET_ACCESS_KEY: ${S3_SECRET_ACCESS_KEY:-}
      S3_BUCKET_NAME: ${S3_BUCKET_NAME:-}
      S3_REGION: ${S3_REGION:-us-east-1}
```

- [ ] **Step 4: Commit**

```bash
git add backend/.env.example backend/docker-compose.yml docker-compose.yml
git commit -m "feat: add S3 config to env, Garage to dev compose, S3 vars to prod compose"
```

---

## Task 6: Verify Everything Works

- [ ] **Step 1: Run pyright on all changed files**

```bash
cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pyright
```
Expected: 0 errors

- [ ] **Step 2: Run ruff**

```bash
cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run ruff check
```
Expected: 0 errors

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pytest
```
Expected: All tests pass

- [ ] **Step 4: Grep for stale references**

```bash
grep -rn "S3FileRepository\|s3_file_repository\|S3_ENDPOINT" src/ tests/ --include="*.py" | head -20
```

Verify all references are intentional and correct.

- [ ] **Step 5: Commit if any fixes needed**

```bash
git commit -m "fix: resolve issues from S3 integration"
```
