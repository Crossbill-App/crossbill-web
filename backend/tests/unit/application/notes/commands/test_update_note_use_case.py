"""Tests for UpdateNoteUseCase live-embedding enqueue hook."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.notes.commands.update_note_use_case import UpdateNoteUseCase
from src.application.semantic.content_type import ContentType


@pytest.fixture
def note() -> MagicMock:
    entity = MagicMock()
    entity.book_ids = [7]
    entity.id = MagicMock(value=100)
    return entity


@pytest.fixture
def note_repository(note: MagicMock) -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = note
    repo.save.return_value = note
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
    link_repository: AsyncMock,
    embedding_enqueuer: AsyncMock,
) -> UpdateNoteUseCase:
    return UpdateNoteUseCase(
        note_repository=note_repository,
        chapter_repository=link_repository,
        highlight_repository=link_repository,
        tag_repository=link_repository,
        embedding_enqueuer=embedding_enqueuer,
    )


async def test_enqueues_note_embedding_after_save(
    use_case: UpdateNoteUseCase, embedding_enqueuer: AsyncMock
) -> None:
    await use_case.update_note(
        note_id=100,
        user_id=5,
        title="t",
        body="b",
        kind=None,
        chapter_ids=[],
        highlight_ids=[],
        tag_ids=[],
    )

    embedding_enqueuer.enqueue_for.assert_awaited_once_with(ContentType.NOTE, 100, 5)


async def test_does_not_enqueue_when_save_fails(
    use_case: UpdateNoteUseCase, note_repository: AsyncMock, embedding_enqueuer: AsyncMock
) -> None:
    note_repository.save.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError):
        await use_case.update_note(
            note_id=100,
            user_id=5,
            title="t",
            body="b",
            kind=None,
            chapter_ids=[],
            highlight_ids=[],
            tag_ids=[],
        )

    embedding_enqueuer.enqueue_for.assert_not_called()
