# FileRepository Protocol Refactor: Path to Bytes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `FileRepositoryProtocol` to return `bytes` instead of `Path`, abstracting away file storage location and preparing for future S3 support.

**Architecture:** The protocol changes from returning `Path` objects to returning `bytes | None` for reads and `str` (filename/key) for writes. All epub infrastructure services change from accepting `Path` to accepting `bytes`. Consumers that only check cover existence use a new `has_cover()` method. The existing local `FileRepository` implementation is updated to match the new protocol.

**Tech Stack:** Python, asyncio, ebooklib (BytesIO support), FastAPI/Starlette, dependency-injector

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/application/library/protocols/file_repository.py` | Protocol: `Path` -> `bytes`/`str` |
| Modify | `src/application/library/protocols/epub_parser.py` | Protocol: `Path` -> `bytes` |
| Modify | `src/application/library/protocols/position_index_service.py` | Protocol: `Path` -> `bytes` |
| Modify | `src/application/reading/protocols/ebook_text_extraction_service.py` | Protocol: `Path` -> `bytes` |
| Modify | `src/infrastructure/library/repositories/file_repository.py` | Implementation: read/write local disk, return bytes/str |
| Modify | `src/infrastructure/library/services/epub_parser_service.py` | Accept `bytes` instead of `Path` |
| Modify | `src/infrastructure/library/services/epub_position_index_service.py` | Accept `bytes` instead of `Path` |
| Modify | `src/infrastructure/library/services/epub_text_extraction_service.py` | Accept `bytes` instead of `Path` |
| Modify | `src/application/library/use_cases/book_files/ebook_upload_use_case.py` | Use `bytes` content directly |
| Modify | `src/application/library/use_cases/book_files/book_cover_use_case.py` | Return `bytes` instead of `Path` |
| Modify | `src/application/reading/use_cases/chapter_content_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/reading/use_cases/chapter_prereading/generate_chapter_prereading_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/jobs/use_cases/enqueue_book_prereading_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/reading/use_cases/highlights/highlight_upload_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/reading/use_cases/reading_sessions/reading_session_upload_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/reading/use_cases/reading_sessions/reading_session_query_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/reading/use_cases/reading_sessions/reading_session_ai_summary_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/learning/use_cases/quiz/start_quiz_session_use_case.py` | Use `get_epub()` -> `bytes` |
| Modify | `src/application/library/use_cases/book_management/get_book_details_use_case.py` | Use `has_cover()` |
| Modify | `src/application/library/use_cases/book_management/update_book_use_case.py` | Use `has_cover()` |
| Modify | `src/application/library/use_cases/book_queries/get_books_with_counts_use_case.py` | Use `has_cover()` |
| Modify | `src/application/library/use_cases/book_queries/get_recently_viewed_books_use_case.py` | Use `has_cover()` |
| Modify | `src/application/library/use_cases/book_queries/get_ereader_metadata_use_case.py` | Use `has_cover()` via protocol |
| Modify | `src/infrastructure/library/routers/books.py` | `Response(content=bytes)` instead of `FileResponse` |
| Modify | `tests/unit/application/jobs/use_cases/test_enqueue_book_prereading_use_case.py` | Update mocks |
| Modify | `tests/test_chapter_content.py` | Update mocks |
| Modify | `tests/test_quiz_sessions.py` | Update mocks |

---

## Task 1: Update FileRepositoryProtocol

**Files:**
- Modify: `src/application/library/protocols/file_repository.py`

- [ ] **Step 1: Update the protocol**

Replace the entire content of `src/application/library/protocols/file_repository.py`:

```python
from typing import Protocol

from src.domain.common.value_objects.ids import BookId


class FileRepositoryProtocol(Protocol):
    async def save_epub(self, book_id: BookId, content: bytes, title: str) -> str: ...

    async def save_pdf(self, book_id: BookId, content: bytes, title: str) -> str: ...

    async def save_cover(self, book_id: BookId, content: bytes) -> str: ...

    async def delete_epub(self, book_id: BookId) -> bool: ...

    async def delete_pdf(self, book_id: BookId) -> bool: ...

    async def delete_cover(self, book_id: BookId) -> bool: ...

    async def get_epub(self, book_id: BookId) -> bytes | None: ...

    async def get_pdf(self, book_id: BookId) -> bytes | None: ...

    async def get_cover(self, book_id: BookId) -> bytes | None: ...

    async def has_cover(self, book_id: BookId) -> bool: ...
```

Key changes:
- `save_*` returns `str` (filename) instead of `Path`
- `find_*` renamed to `get_*`, returns `bytes | None` instead of `Path | None`
- Added `has_cover()` for lightweight existence checks
- Removed `from pathlib import Path` import

- [ ] **Step 2: Commit**

```bash
git add src/application/library/protocols/file_repository.py
git commit -m "refactor: update FileRepositoryProtocol to use bytes instead of Path"
```

---

## Task 2: Update Epub Infrastructure Service Protocols

**Files:**
- Modify: `src/application/library/protocols/epub_parser.py`
- Modify: `src/application/library/protocols/position_index_service.py`
- Modify: `src/application/reading/protocols/ebook_text_extraction_service.py`

- [ ] **Step 1: Update EpubParserProtocol**

Replace the content of `src/application/library/protocols/epub_parser.py`:

```python
from typing import Protocol

from src.domain.library.entities.chapter import TocChapter


class EpubParserProtocol(Protocol):
    def parse_toc(self, epub_content: bytes) -> list[TocChapter]: ...

    def validate_epub(self, content: bytes) -> bool: ...

    def extract_cover(self, epub_content: bytes) -> bytes | None: ...
```

- [ ] **Step 2: Update PositionIndexServiceProtocol**

Replace the content of `src/application/library/protocols/position_index_service.py`:

```python
from typing import Protocol

from src.domain.common.value_objects.position_index import PositionIndex


class PositionIndexServiceProtocol(Protocol):
    def build_position_index(self, epub_content: bytes) -> PositionIndex: ...
```

- [ ] **Step 3: Update EbookTextExtractionServiceProtocol**

Replace the content of `src/application/reading/protocols/ebook_text_extraction_service.py`:

```python
from typing import Protocol


class EbookTextExtractionServiceProtocol(Protocol):
    def extract_text(self, epub_content: bytes, start_xpoint: str, end_xpoint: str) -> str: ...

    def extract_chapter_text(
        self,
        epub_content: bytes,
        start_xpoint: str,
        end_xpoint: str | None,
    ) -> str: ...
```

- [ ] **Step 4: Commit**

```bash
git add src/application/library/protocols/epub_parser.py src/application/library/protocols/position_index_service.py src/application/reading/protocols/ebook_text_extraction_service.py
git commit -m "refactor: update epub service protocols to accept bytes instead of Path"
```

---

## Task 3: Update Epub Infrastructure Service Implementations

**Files:**
- Modify: `src/infrastructure/library/services/epub_parser_service.py`
- Modify: `src/infrastructure/library/services/epub_position_index_service.py`
- Modify: `src/infrastructure/library/services/epub_text_extraction_service.py`

- [ ] **Step 1: Update EpubParserService**

In `src/infrastructure/library/services/epub_parser_service.py`:

Change `parse_toc` signature and implementation (around line 86-98). Replace:
```python
    def parse_toc(self, epub_path: Path) -> list[TocChapter]:
```
with:
```python
    def parse_toc(self, epub_content: bytes) -> list[TocChapter]:
```

Replace the `epub.read_epub(str(epub_path))` call (line 98) with:
```python
            book = epub.read_epub(BytesIO(epub_content))
```

Update all log messages in `parse_toc` that reference `epub_path` to remove the path reference (they can log a generic message or be removed). For example:
- Line 107: `logger.info(f"EPUB at {epub_path} has no table of contents")` -> `logger.info("EPUB has no table of contents")`
- Line 141: `logger.info(f"Parsed {len(result)} chapters from EPUB TOC at {epub_path}")` -> `logger.info(f"Parsed {len(result)} chapters from EPUB TOC")`
- Line 145: `logger.error(f"Failed to parse TOC from EPUB at {epub_path}: {e!s}")` -> `logger.error(f"Failed to parse TOC from EPUB: {e!s}")`

Change `extract_cover` signature and implementation (around line 146-158). Replace:
```python
    def extract_cover(self, epub_path: Path) -> bytes | None:
```
with:
```python
    def extract_cover(self, epub_content: bytes) -> bytes | None:
```

Replace the `epub.read_epub(str(epub_path))` call (line 158) with:
```python
            book = epub.read_epub(BytesIO(epub_content))
```

Update all log messages in `extract_cover` that reference `epub_path` to remove the path reference. For example:
- `f"Extracted cover from OPF metadata for {epub_path}"` -> `"Extracted cover from OPF metadata"`
- `f"Extracted cover from ITEM_COVER for {epub_path}"` -> `"Extracted cover from ITEM_COVER"`
- `f"Extracted cover from OPF meta scan for {epub_path}"` -> `"Extracted cover from OPF meta scan"`
- `f"No cover image found in EPUB {epub_path}"` -> `"No cover image found in EPUB"`
- `f"Failed to extract cover from EPUB {epub_path}: {e!s}"` -> `f"Failed to extract cover from EPUB: {e!s}"`

Remove the `from pathlib import Path` import (line 7) since it's no longer used. `BytesIO` is already imported at line 5.

- [ ] **Step 2: Update EpubPositionIndexService**

In `src/infrastructure/library/services/epub_position_index_service.py`:

Change the method signature (line 17):
```python
    def build_position_index(self, epub_path: Path) -> PositionIndex:
```
to:
```python
    def build_position_index(self, epub_content: bytes) -> PositionIndex:
```

Replace `epub.read_epub(str(epub_path))` (line 30) with:
```python
        book = epub.read_epub(BytesIO(epub_content))
```

Add `from io import BytesIO` to the imports.

Update the log message (around line 62):
```python
        logger.info(
            "Built position index from EPUB",
            extra={
                "total_elements": current_index - 1,
            },
        )
```

Remove `from pathlib import Path` import (line 4).

- [ ] **Step 3: Update EpubTextExtractionService**

In `src/infrastructure/library/services/epub_text_extraction_service.py`:

Change `extract_text` signature (line 26):
```python
    def extract_text(
        self,
        epub_path: Path,
        start_xpoint: str,
        end_xpoint: str,
    ) -> str:
```
to:
```python
    def extract_text(
        self,
        epub_content: bytes,
        start_xpoint: str,
        end_xpoint: str,
    ) -> str:
```

Replace `epub.read_epub(str(epub_path))` (line 50) with:
```python
        epub_book = epub.read_epub(BytesIO(epub_content))
```

Change `extract_chapter_text` signature (line 123):
```python
    def extract_chapter_text(
        self,
        epub_path: Path,
        start_xpoint: str,
        end_xpoint: str | None,
    ) -> str:
```
to:
```python
    def extract_chapter_text(
        self,
        epub_content: bytes,
        start_xpoint: str,
        end_xpoint: str | None,
    ) -> str:
```

Replace `epub.read_epub(str(epub_path))` (line 147) with:
```python
        epub_book = epub.read_epub(BytesIO(epub_content))
```

Add `from io import BytesIO` to the imports.

Remove `from pathlib import Path` import (line 12).

- [ ] **Step 4: Commit**

```bash
git add src/infrastructure/library/services/epub_parser_service.py src/infrastructure/library/services/epub_position_index_service.py src/infrastructure/library/services/epub_text_extraction_service.py
git commit -m "refactor: update epub services to accept bytes instead of Path"
```

---

## Task 4: Update FileRepository Implementation

**Files:**
- Modify: `src/infrastructure/library/repositories/file_repository.py`

- [ ] **Step 1: Update save methods to return str**

In `src/infrastructure/library/repositories/file_repository.py`:

Change `save_epub` return type and return statement (line 43):
```python
    async def save_epub(self, book_id: BookId, content: bytes, title: str) -> str:
```
Change the return statement (line 64) from `return file_path` to:
```python
        return file_path.name
```

Change `save_pdf` return type and return statement (line 66):
```python
    async def save_pdf(self, book_id: BookId, content: bytes, title: str) -> str:
```
Change the return statement (line 83) from `return file_path` to:
```python
        return file_path.name
```

Change `save_cover` return type and return statement (line 85):
```python
    async def save_cover(self, book_id: BookId, content: bytes) -> str:
```
Change the return statement (line 101) from `return file_path` to:
```python
        return file_path.name
```

- [ ] **Step 2: Rename find methods to get methods, return bytes**

Rename `find_epub` to `get_epub` and change return type (line 191):
```python
    async def get_epub(self, book_id: BookId) -> bytes | None:
```

Replace the body (lines 201-208):
```python
        epub_files = await asyncio.to_thread(
            lambda: list(EPUBS_DIR.glob(f"*_{book_id.value}.epub"))
        )

        if not epub_files:
            return None

        return await asyncio.to_thread(epub_files[0].read_bytes)
```

Rename `find_pdf` to `get_pdf` and change return type (line 210):
```python
    async def get_pdf(self, book_id: BookId) -> bytes | None:
```

Replace the body (lines 220-225):
```python
        pdf_files = await asyncio.to_thread(lambda: list(PDFS_DIR.glob(f"*_{book_id.value}.pdf")))

        if not pdf_files:
            return None

        return await asyncio.to_thread(pdf_files[0].read_bytes)
```

Rename `find_cover` to `get_cover` and change return type (line 227):
```python
    async def get_cover(self, book_id: BookId) -> bytes | None:
```

Replace the body (lines 237-245):
```python
        cover_files = await asyncio.to_thread(
            lambda: list(BOOK_COVERS_DIR.glob(f"{book_id.value}.*"))
        )

        if not cover_files:
            return None

        return await asyncio.to_thread(cover_files[0].read_bytes)
```

- [ ] **Step 3: Add has_cover method**

Add this new method at the end of the class:

```python
    async def has_cover(self, book_id: BookId) -> bool:
        """Check if a cover image exists for a book."""
        cover_files = await asyncio.to_thread(
            lambda: list(BOOK_COVERS_DIR.glob(f"{book_id.value}.*"))
        )
        return len(cover_files) > 0
```

- [ ] **Step 4: Clean up imports**

The `Path` import is still needed internally (for type annotations in `_sanitize_title` usage etc.), so keep it. But the return types no longer use `Path`, so double-check no stale references.

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/library/repositories/file_repository.py
git commit -m "refactor: update FileRepository to return bytes/str instead of Path"
```

---

## Task 5: Update EbookUploadUseCase

**Files:**
- Modify: `src/application/library/use_cases/book_files/ebook_upload_use_case.py`

- [ ] **Step 1: Update _upload_epub to use bytes directly**

In `src/application/library/use_cases/book_files/ebook_upload_use_case.py`:

At line 127-128, change:
```python
        epub_path = await self.file_repository.save_epub(book.id, content, book.title)
        book.update_file(epub_path.name, "epub")
```
to:
```python
        epub_filename = await self.file_repository.save_epub(book.id, content, book.title)
        book.update_file(epub_filename, "epub")
```

At line 131, change:
```python
        await self._extract_and_save_cover(book.id, epub_path)
```
to:
```python
        await self._extract_and_save_cover(book.id, content)
```

At line 134, change:
```python
        position_index = self.position_index_service.build_position_index(epub_path)
```
to:
```python
        position_index = self.position_index_service.build_position_index(content)
```

At line 144, change:
```python
        toc_chapters = self.epub_parser.parse_toc(epub_path)
```
to:
```python
        toc_chapters = self.epub_parser.parse_toc(content)
```

At line 168, change:
```python
        return epub_path.name, str(epub_path)
```
to:
```python
        return epub_filename, epub_filename
```

Note: The second return value (`str(epub_path)`) was the absolute path, but the router ignores both return values. The method signature returns `tuple[str, str]` which is preserved. Both values are now the filename since the absolute path concept is no longer meaningful.

- [ ] **Step 2: Update _extract_and_save_cover to accept bytes**

Change the method signature (line 170-174):
```python
    async def _extract_and_save_cover(
        self,
        book_id: BookId,
        epub_path: Path,
    ) -> None:
```
to:
```python
    async def _extract_and_save_cover(
        self,
        book_id: BookId,
        epub_content: bytes,
    ) -> None:
```

Change line 176 from:
```python
        existing_cover = await self.file_repository.find_cover(book_id)
```
to:
```python
        existing_cover = await self.file_repository.has_cover(book_id)
```

Change line 177 from:
```python
        if existing_cover:
```
to:
```python
        if existing_cover:
```
(This stays the same since `has_cover` returns `bool` which is truthy/falsy just like the old `Path | None`.)

Change line 180 from:
```python
        cover_bytes = self.epub_parser.extract_cover(epub_path)
```
to:
```python
        cover_bytes = self.epub_parser.extract_cover(epub_content)
```

- [ ] **Step 3: Remove Path import**

Remove `from pathlib import Path` (line 3) since it's no longer used in this file.

- [ ] **Step 4: Commit**

```bash
git add src/application/library/use_cases/book_files/ebook_upload_use_case.py
git commit -m "refactor: update EbookUploadUseCase to use bytes instead of Path"
```

---

## Task 6: Update BookCoverUseCase and Cover Router

**Files:**
- Modify: `src/application/library/use_cases/book_files/book_cover_use_case.py`
- Modify: `src/infrastructure/library/routers/books.py`

- [ ] **Step 1: Update BookCoverUseCase**

Replace the content of `src/application/library/use_cases/book_files/book_cover_use_case.py`:

```python
"""Book cover management use case."""

import logging

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError

logger = logging.getLogger(__name__)


class BookCoverUseCase:
    """Use case for book cover management operations."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        file_repository: FileRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.file_repository = file_repository

    async def get_cover(self, book_id: int, user_id: int) -> bytes | None:
        """
        Get the cover image bytes with ownership verification.

        Args:
            book_id: ID of the book
            user_id: ID of the user requesting the cover

        Returns:
            Cover image bytes, or None if no cover exists

        Raises:
            BookNotFoundError: If book is not found or user doesn't own it
        """
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        book = await self.book_repository.find_by_id(book_id_vo, user_id_vo)
        if not book:
            raise BookNotFoundError(book_id)

        return await self.file_repository.get_cover(book_id_vo)
```

Note: method renamed from `get_cover_path` to `get_cover`, returns `bytes | None` instead of `Path | None`.

- [ ] **Step 2: Update the cover endpoint in the router**

In `src/infrastructure/library/routers/books.py`, find the cover endpoint (around line 442-469).

Replace:
```python
from starlette.responses import FileResponse
```
with:
```python
from starlette.responses import Response
```

Note: If `FileResponse` is used elsewhere in this file, keep the import and just add `Response`. Check the file first - if `FileResponse` is only used for covers, remove it.

Replace the endpoint (around line 442-469):
```python
@router.get("/{book_id}/cover", status_code=status.HTTP_200_OK)
async def get_book_cover(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: BookCoverUseCase = Depends(inject_use_case(container.library.book_cover_use_case)),
) -> FileResponse:
    cover_path = await use_case.get_cover_path(book_id, current_user.id.value)
    if cover_path is None:
        raise HTTPException(status_code=404, detail="Cover not found")
    return FileResponse(cover_path, media_type="image/jpeg")
```

with:
```python
@router.get("/{book_id}/cover", status_code=status.HTTP_200_OK)
async def get_book_cover(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: BookCoverUseCase = Depends(inject_use_case(container.library.book_cover_use_case)),
) -> Response:
    cover_bytes = await use_case.get_cover(book_id, current_user.id.value)
    if cover_bytes is None:
        raise HTTPException(status_code=404, detail="Cover not found")
    return Response(content=cover_bytes, media_type="image/jpeg")
```

- [ ] **Step 3: Commit**

```bash
git add src/application/library/use_cases/book_files/book_cover_use_case.py src/infrastructure/library/routers/books.py
git commit -m "refactor: update cover use case and router to use bytes instead of Path"
```

---

## Task 7: Update Epub-Consuming Use Cases (Group 1 - Reading)

These use cases all follow the same pattern: `find_epub` -> `.exists()` check -> pass path to service. They all change to: `get_epub` -> None check -> pass bytes to service.

**Files:**
- Modify: `src/application/reading/use_cases/chapter_content_use_case.py`
- Modify: `src/application/reading/use_cases/chapter_prereading/generate_chapter_prereading_use_case.py`
- Modify: `src/application/reading/use_cases/reading_sessions/reading_session_query_use_case.py`
- Modify: `src/application/reading/use_cases/reading_sessions/reading_session_ai_summary_use_case.py`

- [ ] **Step 1: Update ChapterContentUseCase**

In `src/application/reading/use_cases/chapter_content_use_case.py`, lines 66-74:

Replace:
```python
        epub_path = await self.file_repo.find_epub(book.id)
        if not epub_path or not epub_path.exists():
            raise BookNotFoundError(chapter.book_id.value)

        # 4. Extract chapter text
        try:
            content = self.text_extraction.extract_chapter_text(
                epub_path=epub_path,
                start_xpoint=chapter.start_xpoint,
                end_xpoint=chapter.end_xpoint,
            )
```
with:
```python
        epub_content = await self.file_repo.get_epub(book.id)
        if not epub_content:
            raise BookNotFoundError(chapter.book_id.value)

        # 4. Extract chapter text
        try:
            content = self.text_extraction.extract_chapter_text(
                epub_content=epub_content,
                start_xpoint=chapter.start_xpoint,
                end_xpoint=chapter.end_xpoint,
            )
```

- [ ] **Step 2: Update GenerateChapterPrereadingUseCase**

In `src/application/reading/use_cases/chapter_prereading/generate_chapter_prereading_use_case.py`, lines 76-86:

Replace:
```python
        epub_path = await self.file_repo.find_epub(book.id)
        if not epub_path or not epub_path.exists():
            raise BookNotFoundError(chapter.book_id.value)

        # 4. Extract chapter text
        try:
            chapter_text = self.text_extraction.extract_chapter_text(
                epub_path=epub_path,
                start_xpoint=chapter.start_xpoint,
                end_xpoint=chapter.end_xpoint,
            )
```
with:
```python
        epub_content = await self.file_repo.get_epub(book.id)
        if not epub_content:
            raise BookNotFoundError(chapter.book_id.value)

        # 4. Extract chapter text
        try:
            chapter_text = self.text_extraction.extract_chapter_text(
                epub_content=epub_content,
                start_xpoint=chapter.start_xpoint,
                end_xpoint=chapter.end_xpoint,
            )
```

- [ ] **Step 3: Update ReadingSessionQueryUseCase**

In `src/application/reading/use_cases/reading_sessions/reading_session_query_use_case.py`:

At line 106-108, replace:
```python
        epub_path = None
        if include_content and book.file_path and book.file_type == "epub":
            epub_path = await self.file_repo.find_epub(book.id)
```
with:
```python
        epub_content = None
        if include_content and book.file_path and book.file_type == "epub":
            epub_content = await self.file_repo.get_epub(book.id)
```

At line 129-135, replace:
```python
            if include_content and session.start_xpoint and epub_path and epub_path.exists():
                try:
                    extracted_content = self.text_extraction_service.extract_text(
                        epub_path=epub_path,
                        start_xpoint=session.start_xpoint.start.to_string(),
                        end_xpoint=session.start_xpoint.end.to_string(),
                    )
```
with:
```python
            if include_content and session.start_xpoint and epub_content:
                try:
                    extracted_content = self.text_extraction_service.extract_text(
                        epub_content=epub_content,
                        start_xpoint=session.start_xpoint.start.to_string(),
                        end_xpoint=session.start_xpoint.end.to_string(),
                    )
```

- [ ] **Step 4: Update ReadingSessionAISummaryUseCase**

In `src/application/reading/use_cases/reading_sessions/reading_session_ai_summary_use_case.py`, lines 88-96:

Replace:
```python
            epub_path = await self.file_repo.find_epub(book.id)
            if not epub_path or not epub_path.exists():
                raise BookNotFoundError(session.book_id.value)

            content = self.text_extraction_service.extract_text(
                epub_path=epub_path,
                start_xpoint=session.start_xpoint.start.to_string(),
                end_xpoint=session.start_xpoint.end.to_string(),
            )
```
with:
```python
            epub_content = await self.file_repo.get_epub(book.id)
            if not epub_content:
                raise BookNotFoundError(session.book_id.value)

            content = self.text_extraction_service.extract_text(
                epub_content=epub_content,
                start_xpoint=session.start_xpoint.start.to_string(),
                end_xpoint=session.start_xpoint.end.to_string(),
            )
```

- [ ] **Step 5: Commit**

```bash
git add src/application/reading/use_cases/chapter_content_use_case.py src/application/reading/use_cases/chapter_prereading/generate_chapter_prereading_use_case.py src/application/reading/use_cases/reading_sessions/reading_session_query_use_case.py src/application/reading/use_cases/reading_sessions/reading_session_ai_summary_use_case.py
git commit -m "refactor: update reading use cases to use bytes instead of Path"
```

---

## Task 8: Update Epub-Consuming Use Cases (Group 2 - Highlights, Sessions, Jobs, Quiz)

**Files:**
- Modify: `src/application/reading/use_cases/highlights/highlight_upload_use_case.py`
- Modify: `src/application/reading/use_cases/reading_sessions/reading_session_upload_use_case.py`
- Modify: `src/application/jobs/use_cases/enqueue_book_prereading_use_case.py`
- Modify: `src/application/learning/use_cases/quiz/start_quiz_session_use_case.py`

- [ ] **Step 1: Update HighlightUploadUseCase**

In `src/application/reading/use_cases/highlights/highlight_upload_use_case.py`, lines 128-131:

Replace:
```python
        if book.file_type == "epub":
            epub_path = await self.file_repository.find_epub(book.id)
            if epub_path:
                position_index = self.position_index_service.build_position_index(epub_path)
```
with:
```python
        if book.file_type == "epub":
            epub_content = await self.file_repository.get_epub(book.id)
            if epub_content:
                position_index = self.position_index_service.build_position_index(epub_content)
```

- [ ] **Step 2: Update ReadingSessionUploadUseCase**

In `src/application/reading/use_cases/reading_sessions/reading_session_upload_use_case.py`, lines 122-125:

Replace:
```python
        if book.file_type == "epub":
            epub_path = await self.file_repository.find_epub(book.id)
            if epub_path:
                position_index = self.position_index_service.build_position_index(epub_path)
```
with:
```python
        if book.file_type == "epub":
            epub_content = await self.file_repository.get_epub(book.id)
            if epub_content:
                position_index = self.position_index_service.build_position_index(epub_content)
```

- [ ] **Step 3: Update EnqueueBookPrereadingUseCase**

In `src/application/jobs/use_cases/enqueue_book_prereading_use_case.py`, lines 53-71:

Replace:
```python
        epub_path = await self._file_repo.find_epub(book.id)
        if not epub_path or not epub_path.exists():
            raise BookNotFoundError(book_id.value)
```
with:
```python
        epub_content = await self._file_repo.get_epub(book.id)
        if not epub_content:
            raise BookNotFoundError(book_id.value)
```

Replace (around line 69-72):
```python
            try:
                text = self._text_extraction.extract_chapter_text(
                    epub_path=epub_path,
                    start_xpoint=ch.start_xpoint,
                    end_xpoint=ch.end_xpoint,
                )
```
with:
```python
            try:
                text = self._text_extraction.extract_chapter_text(
                    epub_content=epub_content,
                    start_xpoint=ch.start_xpoint,
                    end_xpoint=ch.end_xpoint,
                )
```

- [ ] **Step 4: Update StartQuizSessionUseCase**

In `src/application/learning/use_cases/quiz/start_quiz_session_use_case.py`, lines 67-75:

Replace:
```python
        epub_path = await self.file_repo.find_epub(book.id)
        if not epub_path or not epub_path.exists():
            raise BookNotFoundError(chapter.book_id.value)

        content = self.text_extraction.extract_chapter_text(
            epub_path=epub_path,
            start_xpoint=chapter.start_xpoint,
            end_xpoint=chapter.end_xpoint,
        )
```
with:
```python
        epub_content = await self.file_repo.get_epub(book.id)
        if not epub_content:
            raise BookNotFoundError(chapter.book_id.value)

        content = self.text_extraction.extract_chapter_text(
            epub_content=epub_content,
            start_xpoint=chapter.start_xpoint,
            end_xpoint=chapter.end_xpoint,
        )
```

- [ ] **Step 5: Commit**

```bash
git add src/application/reading/use_cases/highlights/highlight_upload_use_case.py src/application/reading/use_cases/reading_sessions/reading_session_upload_use_case.py src/application/jobs/use_cases/enqueue_book_prereading_use_case.py src/application/learning/use_cases/quiz/start_quiz_session_use_case.py
git commit -m "refactor: update highlight, session, jobs, quiz use cases to use bytes"
```

---

## Task 9: Update Cover Existence Check Use Cases

**Files:**
- Modify: `src/application/library/use_cases/book_management/get_book_details_use_case.py`
- Modify: `src/application/library/use_cases/book_management/update_book_use_case.py`
- Modify: `src/application/library/use_cases/book_queries/get_books_with_counts_use_case.py`
- Modify: `src/application/library/use_cases/book_queries/get_recently_viewed_books_use_case.py`
- Modify: `src/application/library/use_cases/book_queries/get_ereader_metadata_use_case.py`

- [ ] **Step 1: Update GetBookDetailsUseCase**

In `src/application/library/use_cases/book_management/get_book_details_use_case.py`, line 177:

Replace:
```python
        has_cover = await self.file_repository.find_cover(book_id_vo) is not None
```
with:
```python
        has_cover = await self.file_repository.has_cover(book_id_vo)
```

- [ ] **Step 2: Update UpdateBookUseCase**

In `src/application/library/use_cases/book_management/update_book_use_case.py`, line 76:

Replace:
```python
        has_cover = await self.file_repository.find_cover(book_id_vo) is not None
```
with:
```python
        has_cover = await self.file_repository.has_cover(book_id_vo)
```

- [ ] **Step 3: Update GetBooksWithCountsUseCase**

In `src/application/library/use_cases/book_queries/get_books_with_counts_use_case.py`, line 58:

Replace:
```python
                await self.file_repository.find_cover(book.id) is not None,
```
with:
```python
                await self.file_repository.has_cover(book.id),
```

- [ ] **Step 4: Update GetRecentlyViewedBooksUseCase**

In `src/application/library/use_cases/book_queries/get_recently_viewed_books_use_case.py`, line 60:

Replace:
```python
                await self.file_repository.find_cover(book.id) is not None,
```
with:
```python
                await self.file_repository.has_cover(book.id),
```

- [ ] **Step 5: Update GetEreaderMetadataUseCase**

In `src/application/library/use_cases/book_queries/get_ereader_metadata_use_case.py`:

Add `FileRepositoryProtocol` as a dependency. Replace the full file:

```python
"""Get ereader metadata use case."""

from dataclasses import dataclass

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


@dataclass
class EreaderMetadata:
    """Lightweight book metadata for ereader operations."""

    book_id: int
    title: str
    author: str | None
    has_cover: bool
    has_ebook: bool


class GetEreaderMetadataUseCase:
    """Use case for getting ereader metadata."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        file_repository: FileRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.file_repository = file_repository

    async def get_metadata_for_ereader(self, client_book_id: str, user_id: int) -> EreaderMetadata:
        """
        Get basic book metadata for ereader operations.

        Args:
            client_book_id: The client-provided book identifier
            user_id: ID of the user

        Returns:
            EreaderMetadata with book info and file availability flags

        Raises:
            BookNotFoundError: If book is not found for the given client_book_id
        """
        user_id_vo = UserId(user_id)

        book = await self.book_repository.find_by_client_book_id(client_book_id, user_id_vo)
        if not book:
            raise BookNotFoundError(client_book_id)

        has_cover = await self.file_repository.has_cover(book.id)
        has_ebook = book.file_path is not None

        return EreaderMetadata(
            book_id=book.id.value,
            title=book.title,
            author=book.author,
            has_cover=has_cover,
            has_ebook=has_ebook,
        )
```

This removes the hardcoded `COVERS_DIR` path and the `from pathlib import Path` import, and instead uses `FileRepositoryProtocol.has_cover()`.

- [ ] **Step 6: Wire GetEreaderMetadataUseCase in DI container**

In `src/containers/library.py`, find the `GetEreaderMetadataUseCase` factory registration. It currently only receives `book_repository`. Add `file_repository`:

Find:
```python
    get_ereader_metadata_use_case = providers.Factory(
        GetEreaderMetadataUseCase,
        book_repository=book_repository,
    )
```
Replace with:
```python
    get_ereader_metadata_use_case = providers.Factory(
        GetEreaderMetadataUseCase,
        book_repository=book_repository,
        file_repository=file_repository,
    )
```

If the factory only has `book_repository=book_repository` as a single line, add `file_repository=file_repository` as a second parameter.

- [ ] **Step 7: Commit**

```bash
git add src/application/library/use_cases/book_management/get_book_details_use_case.py src/application/library/use_cases/book_management/update_book_use_case.py src/application/library/use_cases/book_queries/get_books_with_counts_use_case.py src/application/library/use_cases/book_queries/get_recently_viewed_books_use_case.py src/application/library/use_cases/book_queries/get_ereader_metadata_use_case.py src/containers/library.py
git commit -m "refactor: update cover existence checks to use has_cover()"
```

---

## Task 10: Update Tests

**Files:**
- Modify: `tests/unit/application/jobs/use_cases/test_enqueue_book_prereading_use_case.py`
- Modify: `tests/test_chapter_content.py`
- Modify: `tests/test_quiz_sessions.py`

- [ ] **Step 1: Update test_enqueue_book_prereading_use_case.py**

In `tests/unit/application/jobs/use_cases/test_enqueue_book_prereading_use_case.py`, find the `file_repo` fixture (around line 70-75):

Replace:
```python
@pytest.fixture
def file_repo() -> AsyncMock:
    repo = AsyncMock()
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    repo.find_epub.return_value = mock_path
    return repo
```
with:
```python
@pytest.fixture
def file_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_epub.return_value = b"fake epub content"
    return repo
```

Remove the `from unittest.mock import MagicMock` import if it's no longer used elsewhere in the file (check first). Remove `from pathlib import Path` if no longer used.

Also search the file for any other references to `find_epub` and replace with `get_epub`. For example, tests that set `file_repo.find_epub.return_value = None` should become `file_repo.get_epub.return_value = None`.

- [ ] **Step 2: Update test_chapter_content.py**

In `tests/test_chapter_content.py`, find the patch for `FileRepository.find_epub` (around line 61-62):

Replace:
```python
    patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.find_epub",
        new_callable=AsyncMock,
    )
```
with:
```python
    patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.get_epub",
        new_callable=AsyncMock,
    )
```

Find where the mock return value is set (the parameter name in the test function). The mock likely returns a `MagicMock(spec=Path)` with `.exists()` returning `True`. Change it to return `b"fake epub content"` instead:

Look for lines like:
```python
    mock_find_epub.return_value = some_path_mock
```
and replace with:
```python
    mock_get_epub.return_value = b"fake epub content"
```

Also update the parameter name in the test function signature from `mock_find_epub` to `mock_get_epub`.

- [ ] **Step 3: Update test_quiz_sessions.py**

In `tests/test_quiz_sessions.py`, find the patch for `FileRepository.find_epub` (around line 33-36):

Replace:
```python
    patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.find_epub",
        new_callable=AsyncMock,
    )
```
with:
```python
    patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.get_epub",
        new_callable=AsyncMock,
    )
```

Update the mock return value from a Path mock to `b"fake epub content"` and update parameter names.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/application/jobs/use_cases/test_enqueue_book_prereading_use_case.py tests/test_chapter_content.py tests/test_quiz_sessions.py
git commit -m "refactor: update tests for bytes-based FileRepository protocol"
```

---

## Task 11: Verify and Fix

- [ ] **Step 1: Run pyright**

```bash
cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pyright
```

Fix any type errors. Common issues to expect:
- Stale `Path` imports that should be removed
- Parameter name mismatches (`epub_path` vs `epub_content`)
- Return type mismatches where code still expects `Path`

- [ ] **Step 2: Run ruff**

```bash
cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run ruff check
```

Fix any linting errors (unused imports of `Path`, etc.).

- [ ] **Step 3: Run tests**

```bash
cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && uv run pytest
```

Fix any test failures. The most likely failures are:
- Mock setups that still reference `find_epub` instead of `get_epub`
- Tests that check for `Path` return types
- Tests that call `.exists()` on return values

- [ ] **Step 4: Grep for stale references**

```bash
cd /Users/tuomas.salmi/Code/crossbill/crossbill-web/backend && grep -rn "find_epub\|find_pdf\|find_cover\|get_cover_path" src/ tests/ --include="*.py"
```

Any remaining references to the old method names must be updated.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve type errors and test failures from protocol refactor"
```
