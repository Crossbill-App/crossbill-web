"""Tests for RelatedContentUseCase (empty when unindexed, else exclude self)."""

from unittest.mock import AsyncMock

import pytest

from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import EmbeddableContent
from src.application.semantic.queries.hydration import overfetch_limit
from src.application.semantic.queries.related_content_use_case import RelatedContentUseCase
from src.application.semantic.queries.semantic_search import SemanticSearchHit


def _embeddable(content_id: int, text: str) -> EmbeddableContent:
    return EmbeddableContent(
        content_type=ContentType.HIGHLIGHT,
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
def content_source() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(query: AsyncMock, content_source: AsyncMock) -> RelatedContentUseCase:
    return RelatedContentUseCase(query=query, content_source=content_source)


class TestRelatedContent:
    async def test_returns_empty_when_vector_missing(
        self, use_case: RelatedContentUseCase, query: AsyncMock
    ) -> None:
        query.get_vector.return_value = None

        results = await use_case.execute(
            content_type=ContentType.NOTE, content_id=5, user_id=1, limit=10
        )

        assert results == []
        query.nearest.assert_not_called()

    async def test_excludes_self_and_hydrates(
        self,
        use_case: RelatedContentUseCase,
        query: AsyncMock,
        content_source: AsyncMock,
    ) -> None:
        query.get_vector.return_value = [0.1, 0.2, 0.3]
        query.nearest.return_value = [
            SemanticSearchHit(
                content_type=ContentType.HIGHLIGHT, content_id=9, book_id=3, score=0.8
            )
        ]
        content_source.get_embeddable.return_value = _embeddable(9, "related text")

        results = await use_case.execute(
            content_type=ContentType.HIGHLIGHT, content_id=5, user_id=1, limit=10
        )

        query.get_vector.assert_awaited_once_with(
            content_type=ContentType.HIGHLIGHT, content_id=5, user_id=1
        )
        query.nearest.assert_awaited_once_with(
            embedding=[0.1, 0.2, 0.3],
            user_id=1,
            book_id=None,
            limit=overfetch_limit(10),
            exclude=(ContentType.HIGHLIGHT, 5),
        )
        assert [(view.content_id, view.text, view.score) for view in results] == [
            (9, "related text", 0.8)
        ]
