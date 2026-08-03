"""Tests for HighlightUploadUseCase live-embedding enqueue hook."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.reading.commands.highlights.highlight_upload_use_case import (
    HighlightUploadData,
    HighlightUploadUseCase,
)
from src.application.semantic.content_type import ContentType


@pytest.fixture
def book() -> MagicMock:
    entity = MagicMock()
    entity.id = MagicMock(value=7)
    entity.file_type = "pdf"
    entity.ebook_file = None
    return entity


@pytest.fixture
def book_repository(book: MagicMock) -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_client_book_id.return_value = book
    return repo


@pytest.fixture
def highlight_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.get_existing_hashes.return_value = []
    repo.bulk_save.return_value = [SimpleNamespace(id=SimpleNamespace(value=55))]
    return repo


@pytest.fixture
def chapter_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_numbers.return_value = {}
    return repo


@pytest.fixture
def deduplication_service() -> MagicMock:
    service = MagicMock()
    service.find_duplicates.side_effect = lambda new, existing: (new, [])
    return service


@pytest.fixture
def highlight_style_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.find_or_create.return_value = MagicMock(id=MagicMock(value=1))
    return repo


@pytest.fixture
def embedding_enqueuer() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(
    highlight_repository: AsyncMock,
    book_repository: AsyncMock,
    chapter_repository: AsyncMock,
    deduplication_service: MagicMock,
    highlight_style_repository: AsyncMock,
    embedding_enqueuer: AsyncMock,
) -> HighlightUploadUseCase:
    return HighlightUploadUseCase(
        highlight_repository=highlight_repository,
        book_repository=book_repository,
        chapter_repository=chapter_repository,
        deduplication_service=deduplication_service,
        position_index_service=MagicMock(),
        file_repository=AsyncMock(),
        highlight_style_repository=highlight_style_repository,
        embedding_enqueuer=embedding_enqueuer,
    )


async def test_enqueues_saved_highlight_ids_as_batch(
    use_case: HighlightUploadUseCase, embedding_enqueuer: AsyncMock
) -> None:
    await use_case.upload_highlights(
        client_book_id="cbid",
        highlight_data_list=[HighlightUploadData(text="hello world")],
        user_id=5,
    )

    embedding_enqueuer.enqueue_many.assert_awaited_once_with(
        ContentType.HIGHLIGHT, [55], 5, reference_id="7"
    )


async def test_does_not_enqueue_when_no_new_highlights(
    use_case: HighlightUploadUseCase,
    deduplication_service: MagicMock,
    embedding_enqueuer: AsyncMock,
) -> None:
    deduplication_service.find_duplicates.side_effect = lambda new, existing: ([], new)

    await use_case.upload_highlights(
        client_book_id="cbid",
        highlight_data_list=[HighlightUploadData(text="hello world")],
        user_id=5,
    )

    embedding_enqueuer.enqueue_many.assert_not_called()


async def test_does_not_enqueue_when_save_fails(
    use_case: HighlightUploadUseCase,
    highlight_repository: AsyncMock,
    embedding_enqueuer: AsyncMock,
) -> None:
    highlight_repository.bulk_save.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError):
        await use_case.upload_highlights(
            client_book_id="cbid",
            highlight_data_list=[HighlightUploadData(text="hello world")],
            user_id=5,
        )

    embedding_enqueuer.enqueue_many.assert_not_called()
