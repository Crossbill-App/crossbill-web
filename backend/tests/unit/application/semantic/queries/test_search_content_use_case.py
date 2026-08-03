"""Tests for SearchContentUseCase (embed once, hydrate in order, drop the gone)."""

from unittest.mock import AsyncMock

import pytest

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import EmbeddableContent
from src.application.semantic.queries.search_content_use_case import SearchContentUseCase
from src.application.semantic.queries.semantic_search import SemanticSearchHit


def _hit(content_id: int, score: float) -> SemanticSearchHit:
    return SemanticSearchHit(
        content_type=ContentType.NOTE, content_id=content_id, book_id=None, score=score
    )


def _embeddable(content_id: int, text: str) -> EmbeddableContent:
    return EmbeddableContent(
        content_type=ContentType.NOTE,
        content_id=content_id,
        user_id=1,
        book_id=None,
        text=text,
        content_hash="h",
    )


@pytest.fixture
def query() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client() -> AsyncMock:
    service = AsyncMock()
    service.embed.return_value = [[0.1, 0.2, 0.3]]
    return service


@pytest.fixture
def content_source() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(
    query: AsyncMock, client: AsyncMock, content_source: AsyncMock
) -> SearchContentUseCase:
    return SearchContentUseCase(query=query, client=client, content_source=content_source)


class TestSearchContent:
    async def test_embeds_query_once_and_hydrates_in_order(
        self,
        use_case: SearchContentUseCase,
        query: AsyncMock,
        client: AsyncMock,
        content_source: AsyncMock,
    ) -> None:
        query.nearest.return_value = [_hit(1, 0.9), _hit(2, 0.7)]
        content_source.get_embeddable_many.return_value = {
            1: _embeddable(1, "first"),
            2: _embeddable(2, "second"),
        }

        results = await use_case.execute(query_text="idea", user_id=1, book_id=None, limit=10)

        client.embed.assert_awaited_once_with(["idea"])
        query.nearest.assert_awaited_once_with(
            embedding=[0.1, 0.2, 0.3], user_id=1, book_id=None, limit=10
        )
        assert [(view.content_id, view.text, view.score) for view in results] == [
            (1, "first", 0.9),
            (2, "second", 0.7),
        ]

    async def test_drops_hit_whose_source_is_gone(
        self,
        use_case: SearchContentUseCase,
        query: AsyncMock,
        content_source: AsyncMock,
    ) -> None:
        query.nearest.return_value = [_hit(1, 0.9), _hit(2, 0.7)]
        # Id 1 is absent from the batch: its source row is gone.
        content_source.get_embeddable_many.return_value = {2: _embeddable(2, "second")}

        results = await use_case.execute(query_text="idea", user_id=1, book_id=None, limit=10)

        assert [view.content_id for view in results] == [2]
