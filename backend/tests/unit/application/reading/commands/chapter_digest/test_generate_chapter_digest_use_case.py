"""Tests for GenerateChapterDigestUseCase live-embedding enqueue hook."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.reading.commands.chapter_digest.generate_chapter_digest_use_case import (
    GenerateChapterDigestUseCase,
)
from src.application.semantic.content_type import ContentType
from src.domain.common.value_objects.ids import ChapterId, UserId


@pytest.fixture
def chapter() -> MagicMock:
    entity = MagicMock()
    entity.start_xpoint = "/body/1"
    entity.end_xpoint = "/body/2"
    entity.book_id = MagicMock(value=7)
    return entity


@pytest.fixture
def digest_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save.return_value = SimpleNamespace(id=SimpleNamespace(value=88))
    return repo


@pytest.fixture
def chapter_repo(chapter: MagicMock) -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = chapter
    return repo


@pytest.fixture
def book_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = MagicMock(ebook_file="book.epub", file_type="epub")
    return repo


@pytest.fixture
def file_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_epub.return_value = b"epub-bytes"
    return repo


@pytest.fixture
def text_extraction_service() -> MagicMock:
    service = MagicMock()
    service.extract_chapter_text.return_value = "chapter text " * 20
    return service


@pytest.fixture
def ai_digest_service() -> AsyncMock:
    service = AsyncMock()
    service.generate_digest.return_value = SimpleNamespace(
        summary="a summary", keypoints=["one", "two"], questions=["why?"]
    )
    return service


@pytest.fixture
def embedding_enqueuer() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(
    digest_repo: AsyncMock,
    chapter_repo: AsyncMock,
    text_extraction_service: MagicMock,
    book_repo: AsyncMock,
    file_repo: AsyncMock,
    ai_digest_service: AsyncMock,
    embedding_enqueuer: AsyncMock,
) -> GenerateChapterDigestUseCase:
    return GenerateChapterDigestUseCase(
        digest_repo=digest_repo,
        chapter_repo=chapter_repo,
        text_extraction_service=text_extraction_service,
        book_repo=book_repo,
        file_repo=file_repo,
        ai_digest_service=ai_digest_service,
        embedding_enqueuer=embedding_enqueuer,
    )


async def test_enqueues_digest_embedding_after_save(
    use_case: GenerateChapterDigestUseCase, embedding_enqueuer: AsyncMock
) -> None:
    await use_case.generate_digest(ChapterId(1), UserId(5))

    embedding_enqueuer.enqueue_for.assert_awaited_once_with(ContentType.DIGEST, 88, 5)


async def test_does_not_enqueue_when_save_fails(
    use_case: GenerateChapterDigestUseCase,
    digest_repo: AsyncMock,
    embedding_enqueuer: AsyncMock,
) -> None:
    digest_repo.save.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError):
        await use_case.generate_digest(ChapterId(1), UserId(5))

    embedding_enqueuer.enqueue_for.assert_not_called()
