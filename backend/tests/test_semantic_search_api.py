"""Tests for the GET /semantic/search and /semantic/related read endpoints."""

import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.semantic.content_type import ContentType
from src.models import Book, Embedding, Highlight, User

ENABLED = "src.infrastructure.common.dependencies.is_embeddings_enabled"


@pytest.fixture
async def override_embedding_client() -> AsyncGenerator[AsyncMock, None]:
    """Stub the embedding client so search embeds the query without a network call."""
    from src.core import container  # noqa: PLC0415

    fake = AsyncMock()
    fake.embed.return_value = [[1.0, 0.0]]
    container.shared.embedding_client.override(fake)
    yield fake
    container.shared.embedding_client.reset_override()


async def _add_embedding(
    db: AsyncSession, highlight: Highlight, vector: list[float], book: Book
) -> None:
    db.add(
        Embedding(
            user_id=highlight.user_id,
            content_type=ContentType.HIGHLIGHT.value,
            content_id=highlight.id,
            book_id=book.id,
            embedding=vector,
            model_name="bge-m3",
            model_version="1",
            content_hash="h" * 64,
        )
    )
    await db.commit()


class TestSearchEndpoint:
    async def test_blocked_when_embeddings_disabled(self, client: AsyncClient) -> None:
        """Deliberately does not override the embedding client.

        With no provider configured, ``build_embedding_client`` raises, so this
        only returns 403 if the feature gate runs before the use case (and its
        client) is constructed. Overriding the client here would mask that.
        """
        with patch(ENABLED, return_value=False):
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
        near = await _make_highlight(db_session, test_book, "near text", vector=[1.0, 0.0])
        far = await _make_highlight(db_session, test_book, "far text", vector=[0.0, 1.0])

        with patch(ENABLED, return_value=True):
            response = await client.get("/api/v1/semantic/search", params={"q": "idea"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ids = [row["content_id"] for row in data]
        assert ids[0] == near.id
        assert far.id in ids
        assert data[0]["score"] >= data[-1]["score"]
        assert data[0]["text"] == "near text"


class TestRelatedEndpoint:
    async def test_blocked_when_embeddings_disabled(self, client: AsyncClient) -> None:
        with patch(ENABLED, return_value=False):
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
        anchor = await _make_highlight(db_session, test_book, "anchor", vector=[1.0, 0.0])
        neighbour = await _make_highlight(db_session, test_book, "neighbour", vector=[0.9, 0.1])

        with patch(ENABLED, return_value=True):
            response = await client.get(
                "/api/v1/semantic/related",
                params={"content_type": "highlight", "content_id": anchor.id},
            )

        assert response.status_code == status.HTTP_200_OK
        ids = [row["content_id"] for row in response.json()]
        assert neighbour.id in ids
        assert anchor.id not in ids

    async def test_returns_empty_when_unit_not_indexed(
        self, client: AsyncClient, test_highlight: Highlight
    ) -> None:
        with patch(ENABLED, return_value=True):
            response = await client.get(
                "/api/v1/semantic/related",
                params={"content_type": "highlight", "content_id": test_highlight.id},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


async def _make_highlight(
    db: AsyncSession, book: Book, text: str, *, vector: list[float]
) -> Highlight:
    highlight = Highlight(
        user_id=book.user_id,
        book_id=book.id,
        text=text,
        datetime="2024-01-15 14:30:22",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )
    db.add(highlight)
    await db.commit()
    await db.refresh(highlight)
    await _add_embedding(db, highlight, vector, book)
    return highlight


class TestResultPaging:
    async def test_fills_the_page_when_an_indexed_source_was_deleted(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A deleted-but-indexed unit must not consume a slot in the page.

        The index stores no source state, so the NN scan still ranks the deleted
        highlight; only hydration can drop it. Ranking exactly `limit` rows would
        hand back one result instead of two.
        """
        best = await _make_highlight(db_session, test_book, "closest", vector=[1.0, 0.0])
        second = await _make_highlight(db_session, test_book, "next", vector=[0.95, 0.05])
        third = await _make_highlight(db_session, test_book, "third", vector=[0.9, 0.1])
        best.deleted_at = datetime.now(UTC)
        await db_session.commit()

        with patch(ENABLED, return_value=True):
            response = await client.get("/api/v1/semantic/search", params={"q": "idea", "limit": 2})

        assert response.status_code == status.HTTP_200_OK
        ids = [row["content_id"] for row in response.json()]
        assert ids == [second.id, third.id]

    async def test_never_returns_more_than_the_requested_limit(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        for index in range(5):
            await _make_highlight(
                db_session, test_book, f"text {index}", vector=[1.0 - index / 10, 0.0]
            )

        with patch(ENABLED, return_value=True):
            response = await client.get("/api/v1/semantic/search", params={"q": "idea", "limit": 2})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    async def test_does_not_return_another_users_content(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A dropped user_id filter is this app's worst realistic bug class."""
        mine = await _make_highlight(db_session, test_book, "mine", vector=[1.0, 0.0])
        other_user = User(email="someone.else@test.com")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        other_book = Book(user_id=other_user.id, title="Someone else's")
        db_session.add(other_book)
        await db_session.commit()
        await db_session.refresh(other_book)
        theirs = await _make_highlight(db_session, other_book, "theirs", vector=[1.0, 0.0])

        with patch(ENABLED, return_value=True):
            response = await client.get("/api/v1/semantic/search", params={"q": "idea"})

        assert response.status_code == status.HTTP_200_OK
        ids = [row["content_id"] for row in response.json()]
        assert mine.id in ids
        assert theirs.id not in ids
