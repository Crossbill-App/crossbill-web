"""Tests for CreateNoteUseCase live-embedding enqueue hook."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.notes.commands.create_note_use_case import CreateNoteUseCase
from src.application.semantic.content_type import ContentType


@pytest.fixture
def note_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.save.return_value = MagicMock(id=MagicMock(value=100))
    return repo


@pytest.fixture
def book_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = MagicMock()
    return repo


@pytest.fixture
def link_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_ids.return_value = []
    return repo


@pytest.fixture
def embedding_enqueuer() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(
    note_repository: AsyncMock,
    book_repository: AsyncMock,
    link_repository: AsyncMock,
    embedding_enqueuer: AsyncMock,
) -> CreateNoteUseCase:
    return CreateNoteUseCase(
        note_repository=note_repository,
        book_repository=book_repository,
        chapter_repository=link_repository,
        highlight_repository=link_repository,
        tag_repository=link_repository,
        embedding_enqueuer=embedding_enqueuer,
    )


async def test_enqueues_note_embedding_after_save(
    use_case: CreateNoteUseCase, embedding_enqueuer: AsyncMock
) -> None:
    await use_case.create_note(
        user_id=5,
        title="t",
        body="b",
        kind=None,
        book_id=7,
        chapter_ids=[],
        highlight_ids=[],
        tag_ids=[],
    )

    embedding_enqueuer.enqueue_for.assert_awaited_once_with(ContentType.NOTE, 100, 5)


async def test_does_not_enqueue_when_save_fails(
    use_case: CreateNoteUseCase, note_repository: AsyncMock, embedding_enqueuer: AsyncMock
) -> None:
    note_repository.save.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError):
        await use_case.create_note(
            user_id=5,
            title="t",
            body="b",
            kind=None,
            book_id=7,
            chapter_ids=[],
            highlight_ids=[],
            tag_ids=[],
        )

    embedding_enqueuer.enqueue_for.assert_not_called()
