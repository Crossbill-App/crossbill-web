"""Tests for GenerateContentEmbeddingsUseCase (the idempotency spine, per slice)."""

from unittest.mock import AsyncMock

import pytest

from src.application.semantic.commands.generate_content_embeddings_use_case import (
    GenerateContentEmbeddingsUseCase,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import EmbeddableContent
from src.application.semantic.protocols.embedding_repository import EmbeddingState
from src.config import get_settings

HASH = "a" * 64


def _embeddable(
    content_id: int = 42, content_hash: str = HASH, text: str = "the text to embed"
) -> EmbeddableContent:
    return EmbeddableContent(
        content_type=ContentType.NOTE,
        content_id=content_id,
        user_id=1,
        book_id=7,
        text=text,
        content_hash=content_hash,
    )


def _current_state(content_hash: str = HASH) -> EmbeddingState:
    settings = get_settings()
    return EmbeddingState(
        content_hash=content_hash,
        model_name=settings.EMBEDDING_MODEL_NAME or "",
        model_version=settings.EMBEDDING_MODEL_VERSION,
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
    repo = AsyncMock()
    repo.get_states.return_value = {}
    return repo


@pytest.fixture
def use_case(
    content_source: AsyncMock, client: AsyncMock, repo: AsyncMock
) -> GenerateContentEmbeddingsUseCase:
    return GenerateContentEmbeddingsUseCase(
        content_source=content_source,
        client=client,
        repo=repo,
        settings=get_settings(),
    )


class TestGenerateContentEmbeddings:
    async def test_skips_when_hash_and_model_unchanged(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        content_source.get_embeddable_many.return_value = {42: _embeddable()}
        repo.get_states.return_value = {42: _current_state()}

        await use_case.execute(ContentType.NOTE, [42])

        client.embed.assert_not_called()
        repo.upsert_many.assert_not_called()

    async def test_deletes_when_source_gone(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        content_source.get_embeddable_many.return_value = {}

        await use_case.execute(ContentType.HIGHLIGHT, [9])

        repo.delete_for.assert_awaited_once_with(ContentType.HIGHLIGHT, [9])
        client.embed.assert_not_called()
        repo.upsert_many.assert_not_called()

    async def test_embeds_and_upserts_when_missing(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        content_source.get_embeddable_many.return_value = {42: _embeddable()}

        await use_case.execute(ContentType.NOTE, [42])

        client.embed.assert_awaited_once_with(["the text to embed"])
        written = repo.upsert_many.await_args.args[0]
        assert len(written) == 1
        assert written[0].content_id == 42
        assert written[0].content_hash == HASH
        assert written[0].embedding == [0.1, 0.2, 0.3]
        assert written[0].book_id == 7

    async def test_re_embeds_when_hash_changed(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        content_source.get_embeddable_many.return_value = {42: _embeddable(content_hash="b" * 64)}
        repo.get_states.return_value = {42: _current_state()}

        await use_case.execute(ContentType.NOTE, [42])

        client.embed.assert_awaited_once()
        repo.upsert_many.assert_awaited_once()


class TestSliceHandling:
    async def test_embeds_a_whole_slice_in_one_model_call(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        """The point of the slice: N units cost one provider request, not N."""
        content_source.get_embeddable_many.return_value = {
            content_id: _embeddable(content_id=content_id, text=f"text {content_id}")
            for content_id in (1, 2, 3)
        }
        client.embed.return_value = [[0.1], [0.2], [0.3]]

        await use_case.execute(ContentType.NOTE, [1, 2, 3])

        client.embed.assert_awaited_once_with(["text 1", "text 2", "text 3"])
        written = repo.upsert_many.await_args.args[0]
        assert [record.content_id for record in written] == [1, 2, 3]
        assert [record.embedding for record in written] == [[0.1], [0.2], [0.3]]

    async def test_embeds_only_the_stale_members_of_a_slice(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        """A slice is not all-or-nothing: current units drop out before the call.

        Without this the TOCTOU re-check could only skip a slice wholesale, so
        one stale unit would pay to re-embed its 31 current neighbours.
        """
        content_source.get_embeddable_many.return_value = {
            content_id: _embeddable(content_id=content_id, text=f"text {content_id}")
            for content_id in (1, 2, 3)
        }
        repo.get_states.return_value = {1: _current_state(), 3: _current_state()}
        client.embed.return_value = [[0.2]]

        await use_case.execute(ContentType.NOTE, [1, 2, 3])

        client.embed.assert_awaited_once_with(["text 2"])
        written = repo.upsert_many.await_args.args[0]
        assert [record.content_id for record in written] == [2]

    async def test_prunes_the_dead_members_and_embeds_the_rest(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        """Orphan sweep and real work can arrive in one slice, and both happen."""
        content_source.get_embeddable_many.return_value = {2: _embeddable(content_id=2)}

        await use_case.execute(ContentType.NOTE, [1, 2, 3])

        repo.delete_for.assert_awaited_once_with(ContentType.NOTE, [1, 3])
        client.embed.assert_awaited_once()
        written = repo.upsert_many.await_args.args[0]
        assert [record.content_id for record in written] == [2]

    async def test_empty_slice_touches_nothing(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        await use_case.execute(ContentType.NOTE, [])

        content_source.get_embeddable_many.assert_not_called()
        repo.delete_for.assert_not_called()
        client.embed.assert_not_called()

    async def test_raises_when_the_client_returns_the_wrong_number_of_vectors(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        content_source: AsyncMock,
        client: AsyncMock,
        repo: AsyncMock,
    ) -> None:
        """A short vector list must not silently write embeddings for a prefix."""
        content_source.get_embeddable_many.return_value = {
            content_id: _embeddable(content_id=content_id) for content_id in (1, 2, 3)
        }
        client.embed.return_value = [[0.1], [0.2]]

        with pytest.raises(ValueError, match="zip"):
            await use_case.execute(ContentType.NOTE, [1, 2, 3])

        repo.upsert_many.assert_not_called()
