"""Tests for the GET /semantic/search and /semantic/related read endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.semantic.content_type import ContentType
from src.infrastructure.semantic.routers.semantic import (
    MAX_QUERY_LENGTH,
    MAX_SEARCH_ITEMS_PER_TYPE,
)
from src.models import Book, Chapter, Highlight, User
from tests.conftest import create_test_book, create_test_highlight
from tests.semantic_helpers import (
    embeddings_disabled,
    get_related,
    get_search,
    plant_indexed_digest,
    plant_indexed_highlight,
    plant_indexed_note,
    plant_one_of_each_type,
    related_groups,
    search_books,
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


class TestContentTypeCoverage:
    def test_every_content_type_has_a_scan_and_a_response_group(self) -> None:
        """Guards the link between ``ContentType`` and ``SearchContentUseCase``.

        ``SearchContentUseCase.execute`` hardcodes ``HIGHLIGHT``/``NOTE``/
        ``DIGEST`` rather than iterating ``ContentType`` -- the right call, since
        the response has three named fields -- but that decouples the enum from
        the scan. ``ContentSource`` *does* iterate ``ContentType`` for the
        backfill, so a fourth member would get indexed while ``/search`` quietly
        never scanned it. This test is what would fail to say so; adding a
        member means adding both a scan and a field to
        ``SearchContentUseCase.execute`` and ``SemanticSearchResultsView``.
        """
        assert set(ContentType) == {ContentType.HIGHLIGHT, ContentType.NOTE, ContentType.DIGEST}


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
        far = await plant_indexed_highlight(db_session, test_book, "far text", vector=[0.8, 0.6])

        response = await get_search(client)

        assert response.status_code == status.HTTP_200_OK
        highlights = response.json()["highlights"]
        ids = [item["id"] for item in highlights]
        assert ids[0] == near.id
        assert far.id in ids
        assert len(ids) == 2  # test_highlight is unindexed and must not surface
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
        highlight, note, digest = await plant_one_of_each_type(db_session, test_book)

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
            db_session, test_book, "Chapter One", vector=[0.8, 0.6]
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

    async def test_digests_are_ordered_by_score_descending(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """Only the highlight group's ordering is pinned elsewhere; every group shares the code path."""
        _, near = await plant_indexed_digest(
            db_session, test_book, "Near Chapter", vector=[1.0, 0.0]
        )
        _, far = await plant_indexed_digest(db_session, test_book, "Far Chapter", vector=[0.8, 0.6])

        groups = await search_groups(client)

        digests = groups["digests"]
        ids = [item["id"] for item in digests]
        assert ids[0] == near.id
        assert far.id in ids
        assert digests[0]["score"] >= digests[-1]["score"]


class TestRenderableFields:
    async def test_highlight_item_carries_its_book_and_chapter(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
        test_chapter: Chapter,
    ) -> None:
        # A spacer highlight keeps highlight.id from coincidentally matching
        # test_chapter.id: both tables' autoincrement starts at 1 in a fresh
        # test database, and the test wants to prove the item carries two
        # genuinely distinct ids.
        await create_test_highlight(
            db_session, test_book, test_book.user_id, "spacer", "2024-01-15 14:29:00"
        )
        highlight = await plant_indexed_highlight(
            db_session, test_book, "the text", vector=[1.0, 0.0]
        )
        highlight.chapter_id = test_chapter.id
        await db_session.commit()

        item = (await search_groups(client))["highlights"][0]

        assert item["id"] == highlight.id
        assert item["id"] != item["chapter_id"]
        assert item["book_id"] == test_book.id
        assert item["book_title"] == "Test Book"
        assert item["chapter_id"] == test_chapter.id
        assert item["chapter_name"] == "Test Chapter"
        assert item["text"] == "the text"
        assert item["page"] == highlight.page
        assert item["datetime"] == highlight.datetime.isoformat()

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
        # A spacer chapter keeps chapter.id from coincidentally matching
        # digest.id: both tables' autoincrement starts at 1 in a fresh test
        # database, and the test wants to prove the item carries two
        # genuinely distinct ids.
        db_session.add(Chapter(book_id=test_book.id, name="Spacer"))
        await db_session.commit()

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
        assert item["id"] != item["chapter_id"]
        assert item["chapter_name"] == "Chapter Seven"
        assert item["chapter_number"] == 7
        assert item["book_id"] == test_book.id
        assert item["book_title"] == "Test Book"
        assert item["summary"] == "What happened"
        assert item["keypoints"] == ["first", "second"]

    async def test_highlight_item_carries_its_books_cover(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A result row shows a cover, and the row's own payload has to carry it."""
        test_book.cover_file = "cover-one.jpg"
        test_book.cover_blurhash = "L6PZfSi_.AyE_3t7t7R**0o#DgR4"
        await plant_indexed_highlight(db_session, test_book, "the text", vector=[1.0, 0.0])
        await db_session.commit()

        item = (await search_groups(client))["highlights"][0]

        assert item["cover_file"] == "cover-one.jpg"
        assert item["cover_blurhash"] == "L6PZfSi_.AyE_3t7t7R**0o#DgR4"

    async def test_digest_item_and_note_books_carry_covers_and_tolerate_none(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """A book with no cover is normal, so both fields must be nullable end to end."""
        second = Book(user_id=test_book.user_id, title="Second Book", cover_file="cover-two.jpg")
        db_session.add(second)
        await db_session.commit()
        await db_session.refresh(second)
        await plant_indexed_digest(
            db_session,
            test_book,
            "Chapter Seven",
            chapter_number=7,
            summary="What happened",
            keypoints=["first"],
            vector=[1.0, 0.0],
        )
        await plant_indexed_note(
            db_session,
            test_book.user_id,
            "A Title",
            body="A body",
            kind="concept",
            books=(test_book, second),
            vector=[1.0, 0.0],
        )

        groups = await search_groups(client)

        # test_book has no cover: null, not a missing key.
        digest = groups["digests"][0]
        assert digest["cover_file"] is None
        assert digest["cover_blurhash"] is None

        covers = {book["title"]: book["cover_file"] for book in groups["notes"][0]["books"]}
        assert covers == {"Test Book": None, "Second Book": "cover-two.jpg"}


class TestBookMatches:
    """Books matched by name, which no amount of embedding similarity would find.

    Nothing here is indexed: the point is that a title or author match stands on
    its own, and the three ranked groups stay empty throughout.
    """

    async def test_matches_a_title_substring_and_carries_what_a_row_renders(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        test_book.cover_file = "cover-one.jpg"
        test_book.cover_blurhash = "L6PZfSi_.AyE_3t7t7R**0o#DgR4"
        await db_session.commit()

        assert await search_books(client, q="est Boo") == [
            {
                "id": test_book.id,
                "title": "Test Book",
                "author": "Test Author",
                "cover_file": "cover-one.jpg",
                "cover_blurhash": "L6PZfSi_.AyE_3t7t7R**0o#DgR4",
            }
        ]

    async def test_matches_an_author_the_title_does_not_contain(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        test_book: Book,
    ) -> None:
        """The query appears only in ``Test Author``, so the title predicate cannot serve it."""
        books = await search_books(client, q="Author")

        assert [book["id"] for book in books] == [test_book.id]

    async def test_matches_regardless_of_case(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        test_book: Book,
    ) -> None:
        books = await search_books(client, q="test book")

        assert [book["id"] for book in books] == [test_book.id]

    async def test_group_is_present_but_empty_when_nothing_matches(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        test_book: Book,
    ) -> None:
        groups = await search_groups(client, q="nothing like a title")

        assert groups["books"] == []

    async def test_a_book_scoped_search_returns_no_books(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        test_book: Book,
    ) -> None:
        """The reader is already inside that book; offering it back says nothing."""
        groups = await search_groups(client, q="Test Book", book_id=test_book.id)

        assert groups["books"] == []

    async def test_does_not_return_another_users_book(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        other_user = User(email="other-library@test.com")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        await create_test_book(db_session, other_user.id, title="Test Bible")

        books = await search_books(client, q="Test")

        assert [book["id"] for book in books] == [test_book.id]

    async def test_caps_the_matches_and_takes_them_in_title_order(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """Created back to front, so insertion order cannot pass for title order."""
        for suffix in reversed("ABCDEF"):
            await create_test_book(db_session, test_book.user_id, title=f"Matcher {suffix}")

        books = await search_books(client, q="Matcher")

        assert [book["title"] for book in books] == [f"Matcher {s}" for s in "ABCDE"]


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

    async def test_does_not_leak_another_users_book_through_a_note_link(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """``note_books`` carries no ownership check of its own; hydration must supply it.

        The note is mine, but its ``note_books`` row points at someone else's
        book -- a shape the association table's foreign keys do not forbid. The
        note itself must still surface; only the leaked book link must not.
        """
        other_user = User(email="book-owner@test.com")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        other_book = Book(user_id=other_user.id, title="Not Yours")
        db_session.add(other_book)
        await db_session.commit()
        await db_session.refresh(other_book)
        note = await plant_indexed_note(
            db_session, test_book.user_id, "Mine", books=(other_book,), vector=[1.0, 0.0]
        )

        groups = await search_groups(client)

        assert [item["id"] for item in groups["notes"]] == [note.id]
        assert groups["notes"][0]["books"] == []


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
        assert len(response.json()["highlights"]) == 1

    async def test_rejects_a_limit_above_the_maximum(
        self, client: AsyncClient, override_embedding_client: AsyncMock
    ) -> None:
        response = await get_search(client, limit=MAX_SEARCH_ITEMS_PER_TYPE + 1)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
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

        groups = await related_groups(client, content_type="highlight", content_id=anchor.id)

        ids = [item["id"] for item in groups["highlights"]]
        assert neighbour.id in ids
        assert anchor.id not in ids

    async def test_ranks_every_type_against_the_anchor(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """The anchor is one type; its neighbours are all of them."""
        anchor, note, digest = await plant_one_of_each_type(db_session, test_book)
        # Each table numbers from 1, so the note shares the anchor's id here. That
        # is the case worth having: self-exclusion is by (type, id) pair, and
        # excluding by id alone would silently drop this note.
        assert note.id == anchor.id, "expected the id sequences to collide"

        groups = await related_groups(client, content_type="highlight", content_id=anchor.id)

        assert [item["id"] for item in groups["notes"]] == [note.id]
        assert [item["id"] for item in groups["digests"]] == [digest.id]

    async def test_returns_empty_groups_when_unit_not_indexed(
        self, client: AsyncClient, test_highlight: Highlight
    ) -> None:
        groups = await related_groups(
            client, content_type="highlight", content_id=test_highlight.id
        )

        assert groups == {"highlights": [], "notes": [], "digests": []}

    async def test_rejects_a_limit_above_the_maximum(
        self, client: AsyncClient, test_highlight: Highlight
    ) -> None:
        response = await get_related(
            client,
            content_type="highlight",
            content_id=test_highlight.id,
            limit=MAX_SEARCH_ITEMS_PER_TYPE + 1,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


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


class TestScoreFloors:
    """Weak matches are dropped, not shown -- and /related is stricter than /search."""

    async def test_search_drops_a_match_below_the_floor(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        strong = await plant_indexed_highlight(db_session, test_book, "on topic", vector=[1.0, 0.0])
        await plant_indexed_highlight(db_session, test_book, "unrelated", vector=[0.2, 1.0])

        assert await search_highlight_ids(client) == [strong.id]

    async def test_search_answers_empty_rather_than_with_the_least_bad_rows(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """What a nonsense query gets: nearest-neighbour search always has an answer."""
        await plant_indexed_highlight(db_session, test_book, "unrelated", vector=[0.2, 1.0])
        await plant_indexed_note(
            db_session, test_book.user_id, "Unrelated", books=(test_book,), vector=[0.1, 1.0]
        )

        assert await search_groups(client) == {
            "highlights": [],
            "notes": [],
            "digests": [],
            "books": [],
        }

    async def test_related_holds_a_higher_floor_than_search(
        self,
        client: AsyncClient,
        override_embedding_client: AsyncMock,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """One match, scoring ~0.49: good enough to answer a question, not to volunteer.

        Both floors read the same score off the same row, so this pins the two
        apart rather than pinning either number -- collapsing them to one value
        would fail here whichever value won.
        """
        anchor = await plant_indexed_highlight(db_session, test_book, "anchor", vector=[1.0, 0.0])
        middling = await plant_indexed_highlight(
            db_session, test_book, "middling", vector=[0.5, 0.9]
        )

        assert middling.id in await search_highlight_ids(client)

        groups = await related_groups(client, content_type="highlight", content_id=anchor.id)
        assert groups["highlights"] == []


async def _plant_two_book_neighbourhood(
    db_session: AsyncSession,
    anchor_book: Book,
    *,
    same_book: int,
    cross_book: int,
) -> tuple[Highlight, Book]:
    """Plant an anchor and equally-scoring neighbours split over two books.

    Every vector is identical, so the ranking is decided by insertion order
    alone: the anchor's own book fills the head of the list and the other book
    follows. That is the arrangement the cap exists to break up, and leaving
    scores out of it keeps the cap the only thing under test.
    """
    anchor = await plant_indexed_highlight(db_session, anchor_book, "anchor", vector=[1.0, 0.0])
    for index in range(same_book):
        await plant_indexed_highlight(db_session, anchor_book, f"same {index}", vector=[1.0, 0.0])

    other_book = Book(user_id=anchor_book.user_id, title="The Other Book")
    db_session.add(other_book)
    await db_session.commit()
    await db_session.refresh(other_book)
    for index in range(cross_book):
        await plant_indexed_highlight(db_session, other_book, f"cross {index}", vector=[1.0, 0.0])

    return anchor, other_book


class TestPerBookCap:
    """Whether one book may fill a related page depends on the anchor's neighbourhood."""

    async def test_spreads_the_page_when_the_neighbourhood_spans_the_library(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """Ten strong cross-book neighbours: the anchor is not an isolated topic.

        The third row proves the page is chosen from more candidates than it
        returns -- it sits at rank six of the raw ranking, which a plain top-five
        could never reach. The page then stops at four of the five asked for,
        because two books can offer no more: a short page is the honest answer,
        and backfilling it is exactly what the cap is refusing to do.
        """
        anchor, other_book = await _plant_two_book_neighbourhood(
            db_session, test_book, same_book=5, cross_book=10
        )

        groups = await related_groups(
            client, content_type="highlight", content_id=anchor.id, limit=5
        )

        assert [item["book_id"] for item in groups["highlights"]] == [
            test_book.id,
            test_book.id,
            other_book.id,
            other_book.id,
        ]

    async def test_leaves_an_isolated_anchor_its_own_books_neighbours(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """One cross-book neighbour fewer, and the cap must not fire.

        A technical book or a novel looks like this: the only passages that
        genuinely relate to a chapter are in the same book, and capping them
        would fill the page with the noise underneath instead.
        """
        anchor, _ = await _plant_two_book_neighbourhood(
            db_session, test_book, same_book=5, cross_book=9
        )

        groups = await related_groups(
            client, content_type="highlight", content_id=anchor.id, limit=5
        )

        assert [item["book_id"] for item in groups["highlights"]] == [test_book.id] * 5


class TestQueryValidation:
    async def test_rejects_empty_query_without_calling_the_model(
        self, client: AsyncClient, override_embedding_client: AsyncMock
    ) -> None:
        """Every query costs a model call, so an empty one must not reach it."""
        response = await get_search(client, q="")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        override_embedding_client.embed.assert_not_called()

    async def test_rejects_overlong_query_without_calling_the_model(
        self, client: AsyncClient, override_embedding_client: AsyncMock
    ) -> None:
        response = await get_search(client, q="x" * (MAX_QUERY_LENGTH + 1))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
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
