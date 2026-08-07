"""Tests for the GET /semantic/search and /semantic/related read endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.semantic.routers.semantic import (
    MAX_QUERY_LENGTH,
    MAX_SEARCH_ITEMS_PER_TYPE,
)
from src.models import Book, Chapter, Highlight, User
from tests.semantic_helpers import (
    embeddings_disabled,
    get_related,
    get_search,
    plant_indexed_digest,
    plant_indexed_highlight,
    plant_indexed_note,
    search_groups,
    search_highlight_ids,
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
        highlights = response.json()["highlights"]
        ids = [item["id"] for item in highlights]
        assert ids[0] == near.id
        assert far.id in ids
        assert highlights[0]["score"] >= highlights[-1]["score"]
        assert highlights[0]["text"] == "near text"


class TestGrouping:
    async def test_returns_every_type_in_its_own_group(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A single ranked list let one type crowd out the others; three scans cannot."""
        highlight = await plant_indexed_highlight(
            db_session, test_book, "a highlight", vector=[1.0, 0.0]
        )
        note = await plant_indexed_note(
            db_session, test_book.user_id, "A Note", books=(test_book,), vector=[0.9, 0.1]
        )
        _, digest = await plant_indexed_digest(
            db_session, test_book, "Chapter One", chapter_number=1, vector=[0.8, 0.2]
        )

        groups = await search_groups(client)

        assert [item["id"] for item in groups["highlights"]] == [highlight.id]
        assert [item["id"] for item in groups["notes"]] == [note.id]
        assert [item["id"] for item in groups["digests"]] == [digest.id]

    async def test_a_crowded_type_does_not_starve_the_others(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """Three highlights outrank the digest; a flat top-2 would have hidden it."""
        for index in range(3):
            await plant_indexed_highlight(
                db_session, test_book, f"highlight {index}", vector=[1.0, 0.0]
            )
        _, digest = await plant_indexed_digest(
            db_session, test_book, "Chapter One", vector=[0.1, 0.9]
        )

        groups = await search_groups(client, limit=2)

        assert len(groups["highlights"]) == 2
        assert [item["id"] for item in groups["digests"]] == [digest.id]

    async def test_empty_groups_are_present_not_omitted(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        await plant_indexed_highlight(db_session, test_book, "only this", vector=[1.0, 0.0])

        groups = await search_groups(client)

        assert groups["notes"] == []
        assert groups["digests"] == []


class TestRenderableFields:
    async def test_highlight_item_carries_its_book_and_chapter(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
        test_chapter: Chapter,
    ) -> None:
        highlight = await plant_indexed_highlight(
            db_session, test_book, "the text", vector=[1.0, 0.0]
        )
        highlight.chapter_id = test_chapter.id
        await db_session.commit()

        item = (await search_groups(client))["highlights"][0]

        assert item["id"] == highlight.id
        assert item["book_id"] == test_book.id
        assert item["book_title"] == "Test Book"
        assert item["chapter_id"] == test_chapter.id
        assert item["chapter_name"] == "Test Chapter"
        assert item["text"] == "the text"
        assert item["page"] == highlight.page
        assert item["datetime"] == highlight.datetime

    async def test_note_item_carries_title_body_and_every_book(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """The old ``text`` field concatenated title and body; a list row needs them apart."""
        second = Book(user_id=test_book.user_id, title="Second Book")
        db_session.add(second)
        await db_session.commit()
        await db_session.refresh(second)
        note = await plant_indexed_note(
            db_session,
            test_book.user_id,
            "A Title",
            body="A body",
            kind="concept",
            books=(test_book, second),
            vector=[1.0, 0.0],
        )

        item = (await search_groups(client))["notes"][0]

        assert item["id"] == note.id
        assert item["title"] == "A Title"
        assert item["body"] == "A body"
        assert item["kind"] == "concept"
        assert {book["id"] for book in item["books"]} == {test_book.id, second.id}
        assert {book["title"] for book in item["books"]} == {"Test Book", "Second Book"}

    async def test_digest_item_carries_the_chapter_it_opens(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """``id`` is the digest; ``chapter_id`` is what the chapter view opens on."""
        chapter, digest = await plant_indexed_digest(
            db_session,
            test_book,
            "Chapter Seven",
            chapter_number=7,
            summary="What happened",
            keypoints=["first", "second"],
            vector=[1.0, 0.0],
        )

        item = (await search_groups(client))["digests"][0]

        assert item["id"] == digest.id
        assert item["chapter_id"] == chapter.id
        assert item["chapter_name"] == "Chapter Seven"
        assert item["chapter_number"] == 7
        assert item["book_id"] == test_book.id
        assert item["book_title"] == "Test Book"
        assert item["summary"] == "What happened"
        assert item["keypoints"] == ["first", "second"]


class TestBookScoping:
    async def test_finds_a_note_linked_to_two_books(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """The embedding's scope is NULL for such a note, so this used to find nothing."""
        second = Book(user_id=test_book.user_id, title="Second Book")
        db_session.add(second)
        await db_session.commit()
        await db_session.refresh(second)
        note = await plant_indexed_note(
            db_session,
            test_book.user_id,
            "Spans two",
            books=(test_book, second),
            vector=[1.0, 0.0],
        )

        groups = await search_groups(client, book_id=test_book.id)

        assert [item["id"] for item in groups["notes"]] == [note.id]

    async def test_excludes_a_note_linked_only_to_another_book(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        other = Book(user_id=test_book.user_id, title="Other Book")
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)
        await plant_indexed_note(
            db_session, test_book.user_id, "Elsewhere", books=(other,), vector=[1.0, 0.0]
        )

        groups = await search_groups(client, book_id=test_book.id)

        assert groups["notes"] == []

    async def test_excludes_another_books_highlights(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        mine = await plant_indexed_highlight(db_session, test_book, "here", vector=[1.0, 0.0])
        other = Book(user_id=test_book.user_id, title="Other Book")
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)
        await plant_indexed_highlight(db_session, other, "elsewhere", vector=[1.0, 0.0])

        assert await search_highlight_ids(client, book_id=test_book.id) == [mine.id]


class TestLimitValidation:
    async def test_accepts_the_maximum_per_type_limit(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        await plant_indexed_highlight(db_session, test_book, "something", vector=[1.0, 0.0])

        response = await get_search(client, limit=MAX_SEARCH_ITEMS_PER_TYPE)

        assert response.status_code == status.HTTP_200_OK

    async def test_rejects_a_limit_above_the_maximum(
        self, client: AsyncClient, override_embedding_client: AsyncMock
    ) -> None:
        response = await get_search(client, limit=MAX_SEARCH_ITEMS_PER_TYPE + 1)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        override_embedding_client.embed.assert_not_called()


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

        assert await search_highlight_ids(client) == [visible.id]

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

        assert len(await search_highlight_ids(client, limit=2)) == 2

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

        ids = await search_highlight_ids(client)

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
