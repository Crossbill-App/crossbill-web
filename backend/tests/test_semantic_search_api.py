"""Tests for the GET /semantic/search and /semantic/related read endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.semantic.routers.semantic import MAX_QUERY_LENGTH
from src.models import Book, Highlight, User
from tests.semantic_helpers import (
    embeddings_disabled,
    get_related,
    get_search,
    plant_indexed_highlight,
    search_content_ids,
)


@pytest.fixture
async def override_embedding_client() -> AsyncGenerator[AsyncMock, None]:
    """Stub the embedding client so search embeds the query without a network call."""
    from src.core import container  # noqa: PLC0415

    fake = AsyncMock()
    fake.embed.return_value = [[1.0, 0.0]]
    container.shared.embedding_client.override(fake)
    yield fake
    container.shared.embedding_client.reset_override()


class TestSearchEndpoint:
    async def test_blocked_when_embeddings_disabled(self, client: AsyncClient) -> None:
        """Deliberately does not override the embedding client.

        With no provider configured ``build_embedding_client`` raises, and this
        endpoint injects a use case that holds a client. So the 403 depends on
        that construction being deferred past the gate, which is what
        ``LazyEmbeddingClient`` buys. Overriding the client would mask it, and
        the endpoint would answer 500 in production while the test passed.
        """
        with embeddings_disabled():
            response = await client.get("/api/v1/semantic/search", params={"q": "idea"})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_returns_ranked_results(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
        test_highlight: Highlight,
    ) -> None:
        near = await plant_indexed_highlight(db_session, test_book, "near text", vector=[1.0, 0.0])
        far = await plant_indexed_highlight(db_session, test_book, "far text", vector=[0.0, 1.0])

        response = await get_search(client)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ids = [row["content_id"] for row in data]
        assert ids[0] == near.id
        assert far.id in ids
        assert data[0]["score"] >= data[-1]["score"]
        assert data[0]["text"] == "near text"


class TestRelatedEndpoint:
    async def test_blocked_when_embeddings_disabled(self, client: AsyncClient) -> None:
        with embeddings_disabled():
            response = await client.get(
                "/api/v1/semantic/related",
                params={"content_type": "highlight", "content_id": 1},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_returns_related_excluding_self(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        anchor = await plant_indexed_highlight(db_session, test_book, "anchor", vector=[1.0, 0.0])
        neighbour = await plant_indexed_highlight(
            db_session, test_book, "neighbour", vector=[0.9, 0.1]
        )

        response = await get_related(client, content_type="highlight", content_id=anchor.id)

        assert response.status_code == status.HTTP_200_OK
        ids = [row["content_id"] for row in response.json()]
        assert neighbour.id in ids
        assert anchor.id not in ids

    async def test_returns_empty_when_unit_not_indexed(
        self, client: AsyncClient, test_highlight: Highlight
    ) -> None:
        response = await get_related(client, content_type="highlight", content_id=test_highlight.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestResultPaging:
    async def test_never_returns_content_whose_source_was_deleted(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """The guarantee that deleted content never surfaces, not a safety net.

        Soft-deleting a highlight leaves the row in place, so no foreign key can
        prune its embedding and nothing does so at the delete site: it stays
        indexed until the next backfill sweep. Here it ranks first and must
        still not be shown.
        """
        hidden = await plant_indexed_highlight(db_session, test_book, "deleted", vector=[1.0, 0.0])
        visible = await plant_indexed_highlight(db_session, test_book, "kept", vector=[0.95, 0.05])
        hidden.deleted_at = datetime.now(UTC)
        await db_session.commit()

        assert await search_content_ids(client) == [visible.id]

    async def test_never_returns_more_than_the_requested_limit(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        for index in range(5):
            await plant_indexed_highlight(
                db_session, test_book, f"text {index}", vector=[1.0 - index / 10, 0.0]
            )

        assert len(await search_content_ids(client, limit=2)) == 2

    async def test_does_not_return_another_users_content(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A dropped user_id filter is this app's worst realistic bug class."""
        mine = await plant_indexed_highlight(db_session, test_book, "mine", vector=[1.0, 0.0])
        other_user = User(email="someone.else@test.com")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        other_book = Book(user_id=other_user.id, title="Someone else's")
        db_session.add(other_book)
        await db_session.commit()
        await db_session.refresh(other_book)
        theirs = await plant_indexed_highlight(db_session, other_book, "theirs", vector=[1.0, 0.0])

        ids = await search_content_ids(client)

        assert mine.id in ids
        assert theirs.id not in ids


class TestQueryValidation:
    async def test_rejects_empty_query_without_calling_the_model(
        self, client: AsyncClient, override_embedding_client: AsyncMock
    ) -> None:
        """Every query costs a model call, so an empty one must not reach it."""
        response = await get_search(client, q="")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        override_embedding_client.embed.assert_not_called()

    async def test_rejects_overlong_query_without_calling_the_model(
        self, client: AsyncClient, override_embedding_client: AsyncMock
    ) -> None:
        response = await get_search(client, q="x" * (MAX_QUERY_LENGTH + 1))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        override_embedding_client.embed.assert_not_called()

    async def test_accepts_a_query_at_the_limit(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        await plant_indexed_highlight(db_session, test_book, "something", vector=[1.0, 0.0])

        response = await get_search(client, q="x" * MAX_QUERY_LENGTH)

        assert response.status_code == status.HTTP_200_OK
        override_embedding_client.embed.assert_awaited_once()
