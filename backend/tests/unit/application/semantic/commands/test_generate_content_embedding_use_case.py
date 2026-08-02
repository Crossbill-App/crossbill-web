"""Tests for GenerateContentEmbeddingUseCase (the idempotency spine)."""

from unittest.mock import AsyncMock

import pytest

from src.application.semantic.commands.generate_content_embedding_use_case import (
    GenerateContentEmbeddingUseCase,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import EmbeddableContent
from src.application.semantic.protocols.embedding_repository import EmbeddingState
from src.config import get_settings

HASH = "a" * 64


def _embeddable(content_hash: str = HASH) -> EmbeddableContent:
    return EmbeddableContent(
        content_type=ContentType.NOTE,
        content_id=42,
        user_id=1,
        book_id=7,
        text="the text to embed",
        content_hash=content_hash,
    )


@pytest.fixture
def content_source() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client() -> AsyncMock:
    service = AsyncMock()
    service.embed.return_value = [[0.1, 0.2, 0.3]]
    return service


@pytest.fixture
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(
    content_source: AsyncMock, client: AsyncMock, repo: AsyncMock
) -> GenerateContentEmbeddingUseCase:
    settings = get_settings()
    return GenerateContentEmbeddingUseCase(
        content_source=content_source,
        client=client,
        repo=repo,
        settings=settings,
    )


class TestGenerateContentEmbedding:
    async def test_skips_when_hash_and_model_unchanged(
        self,
        use_case: GenerateContentEmbeddingUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        settings = get_settings()
        content_source.get_embeddable.return_value = _embeddable()
        repo.get_state.return_value = EmbeddingState(
            content_hash=HASH,
            model_name=settings.EMBEDDING_MODEL_NAME or "",
            model_version=settings.EMBEDDING_MODEL_VERSION,
        )

        await use_case.execute(ContentType.NOTE, 42)

        client.embed.assert_not_called()
        repo.upsert.assert_not_called()

    async def test_deletes_when_source_gone(
        self,
        use_case: GenerateContentEmbeddingUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        content_source.get_embeddable.return_value = None

        await use_case.execute(ContentType.HIGHLIGHT, 9)

        repo.delete_for.assert_awaited_once_with(ContentType.HIGHLIGHT, 9)
        client.embed.assert_not_called()
        repo.upsert.assert_not_called()

    async def test_embeds_and_upserts_when_missing(
        self,
        use_case: GenerateContentEmbeddingUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        content_source.get_embeddable.return_value = _embeddable()
        repo.get_state.return_value = None

        await use_case.execute(ContentType.NOTE, 42)

        client.embed.assert_awaited_once_with(["the text to embed"])
        repo.upsert.assert_awaited_once()
        written = repo.upsert.await_args.args[0]
        assert written.content_id == 42
        assert written.content_hash == HASH
        assert written.embedding == [0.1, 0.2, 0.3]
        assert written.book_id == 7

    async def test_re_embeds_when_hash_changed(
        self,
        use_case: GenerateContentEmbeddingUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        settings = get_settings()
        content_source.get_embeddable.return_value = _embeddable(content_hash="b" * 64)
        repo.get_state.return_value = EmbeddingState(
            content_hash=HASH,
            model_name=settings.EMBEDDING_MODEL_NAME or "",
            model_version=settings.EMBEDDING_MODEL_VERSION,
        )

        await use_case.execute(ContentType.NOTE, 42)

        client.embed.assert_awaited_once()
        repo.upsert.assert_awaited_once()
