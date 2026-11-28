"""Tests for Flashcard Reviews, suspending cards, and the queue of Due Flashcards."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.domain.common.value_objects.ids import FlashcardId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.services.due_flashcards import is_due
from src.infrastructure.learning.repositories.flashcard_repository import FlashcardRepository
from src.infrastructure.learning.services.fsrs_review_scheduler import FsrsReviewScheduler
from tests.conftest import (
    create_test_book,
    create_test_chapter,
    create_test_flashcard,
    create_test_highlight,
    plant_note,
    readers_now,
)

T = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def unfuzzed_scheduler() -> Iterator[None]:
    """Schedule without fuzz, so a due date is the one FSRS computes."""
    from src.core import container  # noqa: PLC0415

    container.shared.review_scheduler.override(FsrsReviewScheduler(enable_fuzzing=False))
    yield
    container.shared.review_scheduler.reset_override()


@pytest.fixture
async def other_users_card(db_session: AsyncSession, other_user: models.User) -> models.Flashcard:
    their_book = await create_test_book(db_session, other_user.id, "Their Book")
    return await create_test_flashcard(db_session, their_book)


async def post_review(
    client: AsyncClient, flashcard_id: int, rating: str, reviewed_at: datetime
) -> Response:
    return await client.post(
        f"/api/v1/flashcards/{flashcard_id}/reviews",
        json={"rating": rating, "reviewed_at": reviewed_at.isoformat()},
    )


async def record_review(
    client: AsyncClient, flashcard_id: int, rating: str, reviewed_at: datetime
) -> dict[str, object]:
    response = await post_review(client, flashcard_id, rating, reviewed_at)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def at(value: object) -> datetime:
    """Read a timestamp from a response."""
    assert isinstance(value, str)
    return datetime.fromisoformat(value)


class TestRecordReview:
    async def test_good_on_a_new_card_schedules_it_two_days_out(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        card = await record_review(client, test_flashcard.id, "good", T)

        assert at(card["due"]) == T + timedelta(days=2)
        assert at(card["last_review"]) == T
        assert card["status"] == "active"
        assert card["origin"] == "manual"

    async def test_again_on_a_new_card_brings_it_back_after_the_learning_step(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        card = await record_review(client, test_flashcard.id, "again", T)

        assert at(card["due"]) == T + timedelta(hours=8)

    async def test_good_on_a_graduated_card_stretches_the_interval(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        await record_review(client, test_flashcard.id, "good", T)
        card = await record_review(client, test_flashcard.id, "good", T + timedelta(days=2))

        assert at(card["due"]) == T + timedelta(days=13)

    async def test_a_resent_review_changes_nothing(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        first = await record_review(client, test_flashcard.id, "easy", T)
        resent = await record_review(client, test_flashcard.id, "easy", T)

        assert resent == first
        assert at(resent["due"]) == T + timedelta(days=8)

    async def test_a_late_review_leaves_the_card_as_in_order_arrival_would(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        in_order = await create_test_flashcard(db_session, test_book)
        late = await create_test_flashcard(db_session, test_book)
        reviews = [("good", T), ("again", T + timedelta(days=2)), ("good", T + timedelta(days=3))]

        expected = [await record_review(client, in_order.id, *review) for review in reviews]
        arrived = [
            await record_review(client, late.id, *review)
            for review in (reviews[0], reviews[2], reviews[1])
        ]

        actual = arrived[-1]
        assert (at(actual["due"]), at(actual["last_review"])) == (
            at(expected[-1]["due"]),
            at(expected[-1]["last_review"]),
        )
        assert at(actual["last_review"]) == T + timedelta(days=3)

    async def test_another_users_card_cannot_be_reviewed(
        self, client: AsyncClient, other_users_card: models.Flashcard
    ) -> None:
        response = await post_review(client, other_users_card.id, "good", T)

        assert response.status_code == status.HTTP_404_NOT_FOUND


async def set_status(client: AsyncClient, flashcard_id: int, new_status: str) -> dict[str, object]:
    response = await client.put(
        f"/api/v1/flashcards/{flashcard_id}/status", json={"status": new_status}
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


class TestFlashcardStatus:
    async def test_a_suspended_card_shows_as_suspended_in_the_books_list(
        self, client: AsyncClient, test_book: models.Book, test_flashcard: models.Flashcard
    ) -> None:
        card = await set_status(client, test_flashcard.id, "suspended")

        assert card["status"] == "suspended"
        listed = (await client.get(f"/api/v1/books/{test_book.id}/flashcards")).json()["items"]
        assert [item["status"] for item in listed] == ["suspended"]

    async def test_a_suspended_card_takes_no_review(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        await set_status(client, test_flashcard.id, "suspended")

        response = await post_review(client, test_flashcard.id, "good", T)

        assert response.status_code == status.HTTP_409_CONFLICT
        unsuspended = await set_status(client, test_flashcard.id, "active")
        assert unsuspended["last_review"] is None

    async def test_a_review_resent_after_suspending_changes_nothing(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        first = await record_review(client, test_flashcard.id, "easy", T)
        await set_status(client, test_flashcard.id, "suspended")

        resent = await record_review(client, test_flashcard.id, "easy", T)

        assert resent == first | {"status": "suspended"}
        assert at(resent["due"]) == T + timedelta(days=8)
        later = await post_review(client, test_flashcard.id, "good", T + timedelta(days=8))
        assert later.status_code == status.HTTP_409_CONFLICT

    async def test_unsuspending_keeps_the_cards_schedule(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        await record_review(client, test_flashcard.id, "good", T)
        await set_status(client, test_flashcard.id, "suspended")

        card = await set_status(client, test_flashcard.id, "active")

        assert card["status"] == "active"
        assert at(card["due"]) == T + timedelta(days=2)

    async def test_editing_a_suspended_card_keeps_it_suspended(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        await set_status(client, test_flashcard.id, "suspended")

        response = await client.put(
            f"/api/v1/flashcards/{test_flashcard.id}", json={"question": "Sharper question"}
        )

        assert response.json()["flashcard"]["status"] == "suspended"

    async def test_another_users_card_cannot_be_suspended(
        self, client: AsyncClient, other_users_card: models.Flashcard
    ) -> None:
        response = await client.put(
            f"/api/v1/flashcards/{other_users_card.id}/status", json={"status": "suspended"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


NOW = T + timedelta(days=10)


async def load_flashcard(db_session: AsyncSession, card: models.Flashcard) -> Flashcard:
    loaded = await FlashcardRepository(db_session).find_by_id(
        FlashcardId(card.id), UserId(card.user_id)
    )
    assert loaded is not None
    return loaded


def retrievability_key(card: Flashcard, now: datetime) -> float:
    assert card.review_state is not None
    return card.review_state.retrievability_key(now)


async def get_due(client: AsyncClient, **params: int) -> Response:
    with readers_now(NOW):
        return await client.get("/api/v1/flashcards/due", params=params)


async def due_ids(client: AsyncClient, **params: int) -> list[int]:
    response = await get_due(client, **params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return [item["id"] for item in response.json()["items"]]


class TestDueFlashcards:
    async def test_due_reviews_come_lowest_retrievability_first_then_new_cards_in_book_order(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        chapter_two = await create_test_chapter(db_session, test_book, "Two", chapter_number=2)
        chapter_one = await create_test_chapter(db_session, test_book, "One", chapter_number=1)
        highlight = await create_test_highlight(
            db_session,
            test_book,
            test_book.user_id,
            "Text",
            "2026-10-01 10:00:00",
            chapter_id=chapter_one.id,
        )
        long_overdue = await create_test_flashcard(db_session, test_book)
        just_forgotten = await create_test_flashcard(db_session, test_book)
        await record_review(client, long_overdue.id, "good", T)
        await record_review(client, just_forgotten.id, "again", NOW - timedelta(days=1))
        chapterless = await create_test_flashcard(
            db_session, test_book, created_at=T - timedelta(days=5)
        )
        in_chapter_two = await create_test_flashcard(
            db_session, test_book, chapter_id=chapter_two.id, created_at=T - timedelta(days=4)
        )
        via_highlight = await create_test_flashcard(
            db_session, test_book, highlight_id=highlight.id, created_at=T - timedelta(days=2)
        )
        in_chapter_one = await create_test_flashcard(
            db_session, test_book, chapter_id=chapter_one.id, created_at=T - timedelta(days=3)
        )

        assert await due_ids(client) == [
            just_forgotten.id,
            long_overdue.id,
            in_chapter_one.id,
            via_highlight.id,
            in_chapter_two.id,
            chapterless.id,
        ]

    async def test_new_cards_keep_to_one_book_at_a_time(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        other_book = await create_test_book(db_session, test_book.user_id, "Other Book")
        first_chapter = await create_test_chapter(db_session, test_book, "One", chapter_number=1)
        second_chapter = await create_test_chapter(db_session, test_book, "Two", chapter_number=2)
        other_first = await create_test_chapter(db_session, other_book, "One", chapter_number=1)
        later_in_book = await create_test_flashcard(
            db_session, test_book, chapter_id=second_chapter.id
        )
        in_other_book = await create_test_flashcard(
            db_session, other_book, chapter_id=other_first.id
        )
        early_in_book = await create_test_flashcard(
            db_session, test_book, chapter_id=first_chapter.id
        )

        assert await due_ids(client) == [early_in_book.id, later_in_book.id, in_other_book.id]

    async def test_cards_not_yet_due_and_suspended_cards_stay_out(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        due = await create_test_flashcard(db_session, test_book)
        not_yet_due = await create_test_flashcard(db_session, test_book)
        suspended = await create_test_flashcard(db_session, test_book)
        suspended_due = await create_test_flashcard(db_session, test_book)
        await record_review(client, due.id, "good", T)
        await record_review(client, not_yet_due.id, "good", NOW - timedelta(days=1))
        await record_review(client, suspended_due.id, "good", T)
        await set_status(client, suspended.id, "suspended")
        await set_status(client, suspended_due.id, "suspended")

        assert await due_ids(client) == [due.id]

    async def test_the_queue_follows_the_domains_due_rule_and_retrievability_key(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        cards = [await create_test_flashcard(db_session, test_book) for _ in range(6)]
        await record_review(client, cards[0].id, "good", T)
        await record_review(client, cards[1].id, "again", NOW - timedelta(days=1))
        await record_review(client, cards[2].id, "good", NOW - timedelta(days=1))
        await record_review(client, cards[3].id, "hard", NOW - timedelta(days=3))
        await set_status(client, cards[4].id, "suspended")
        loaded = [await load_flashcard(db_session, card) for card in cards]

        due = [card for card in loaded if is_due(card, NOW)]
        due_reviews = sorted(
            (card for card in due if card.review_state),
            key=lambda card: retrievability_key(card, NOW),
            reverse=True,
        )
        new_cards = [card for card in due if card.review_state is None]
        assert await due_ids(client) == [card.id.value for card in due_reviews + new_cards]
        assert len(due) == 4

    async def test_the_queue_shows_a_cards_schedule_as_its_review_did(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        reviewed = await record_review(client, test_flashcard.id, "good", T)

        (queued,) = (await get_due(client)).json()["items"]

        assert (queued["due"], queued["last_review"]) == (
            reviewed["due"],
            reviewed["last_review"],
        )

    async def test_the_queue_narrows_to_one_book(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        other_book = await create_test_book(db_session, test_book.user_id, "Other Book")
        in_book = await create_test_flashcard(db_session, test_book)
        await create_test_flashcard(db_session, other_book)

        assert await due_ids(client, book_id=test_book.id) == [in_book.id]

    async def test_the_queue_pages_with_its_full_total(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        cards = [await create_test_flashcard(db_session, test_book) for _ in range(3)]

        response = await get_due(client, limit=1, offset=1)

        page = response.json()
        assert [item["id"] for item in page["items"]] == [cards[1].id]
        assert (page["total"], page["offset"], page["limit"]) == (3, 1, 1)

    async def test_another_users_cards_never_appear(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        other_users_card: models.Flashcard,
    ) -> None:
        mine = await create_test_flashcard(db_session, test_book)

        assert await due_ids(client) == [mine.id]
        response = await get_due(client, book_id=other_users_card.book_id)
        assert response.status_code == status.HTTP_404_NOT_FOUND


def context(item: dict[str, object]) -> tuple[object, ...]:
    return (item["book_title"], item["chapter_name"], item["highlight_text"], item["note_title"])


class TestReviewContext:
    async def test_a_due_flashcard_carries_its_book_chapter_and_source(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        chapter = await create_test_chapter(db_session, test_book, "Openings", chapter_number=1)
        highlight = await create_test_highlight(
            db_session,
            test_book,
            test_book.user_id,
            "The marked passage",
            "2026-10-01 10:00:00",
            chapter_id=chapter.id,
        )
        note = await plant_note(db_session, test_book, "Gambits")
        from_highlight = await create_test_flashcard(
            db_session, test_book, highlight_id=highlight.id
        )
        from_note = await create_test_flashcard(db_session, test_book, note_id=note.id)
        from_chapter = await create_test_flashcard(db_session, test_book, chapter_id=chapter.id)
        standalone = await create_test_flashcard(db_session, test_book)

        items = {item["id"]: item for item in (await get_due(client)).json()["items"]}

        assert context(items[from_highlight.id]) == (
            "Test Book",
            "Openings",
            "The marked passage",
            None,
        )
        assert context(items[from_note.id]) == ("Test Book", None, None, "Gambits")
        assert context(items[from_chapter.id]) == ("Test Book", "Openings", None, None)
        assert context(items[standalone.id]) == ("Test Book", None, None, None)

    async def test_a_flashcards_own_chapter_wins_over_its_highlights(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        own = await create_test_chapter(db_session, test_book, "Own", chapter_number=2)
        elsewhere = await create_test_chapter(db_session, test_book, "Elsewhere", chapter_number=1)
        highlight = await create_test_highlight(
            db_session,
            test_book,
            test_book.user_id,
            "Text",
            "2026-10-01 10:00:00",
            chapter_id=elsewhere.id,
        )
        await create_test_flashcard(
            db_session, test_book, chapter_id=own.id, highlight_id=highlight.id
        )

        (item,) = (await get_due(client)).json()["items"]

        assert item["chapter_name"] == "Own"

    async def test_a_deleted_highlight_shows_no_text(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        highlight = await create_test_highlight(
            db_session,
            test_book,
            test_book.user_id,
            "Gone",
            "2026-10-01 10:00:00",
            deleted_at=T,
        )
        await create_test_flashcard(db_session, test_book, highlight_id=highlight.id)

        (item,) = (await get_due(client)).json()["items"]

        assert item["highlight_text"] is None


RATINGS = ("again", "hard", "good", "easy")


class TestRatingPreviews:
    @pytest.mark.parametrize(
        "earlier_ratings", [(), ("again",), ("good",)], ids=["new", "learning", "reviewed"]
    )
    async def test_each_preview_is_the_due_that_recording_that_rating_produces(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        earlier_ratings: tuple[str, ...],
    ) -> None:
        cards = [await create_test_flashcard(db_session, test_book) for _ in RATINGS]
        for card in cards:
            for rating in earlier_ratings:
                await record_review(client, card.id, rating, T)

        previews = [item["previews"] for item in (await get_due(client)).json()["items"]]

        recorded = {
            rating: at((await record_review(client, card.id, rating, NOW))["due"])
            for rating, card in zip(RATINGS, cards, strict=True)
        }
        assert len(previews) == len(RATINGS)
        assert all({r: at(p[r]) for r in RATINGS} == recorded for p in previews)
        assert len(set(recorded.values())) == len(RATINGS)


async def get_suspended(client: AsyncClient, **params: int) -> Response:
    return await client.get("/api/v1/flashcards/suspended", params=params)


async def suspended_ids(client: AsyncClient, **params: int) -> list[int]:
    response = await get_suspended(client, **params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return [item["id"] for item in response.json()["items"]]


async def suspended_flashcard(
    db_session: AsyncSession,
    book: models.Book,
    chapter_id: int | None = None,
    created_at: datetime = T,
) -> int:
    card = await create_test_flashcard(
        db_session, book, status="suspended", chapter_id=chapter_id, created_at=created_at
    )
    return card.id


class TestSuspendedFlashcards:
    async def test_only_suspended_flashcards_are_listed_book_by_book_in_book_order(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        other_book = await create_test_book(db_session, test_book.user_id, "Other Book")
        one = await create_test_chapter(db_session, test_book, "One", chapter_number=1)
        two = await create_test_chapter(db_session, test_book, "Two", chapter_number=2)
        await create_test_flashcard(db_session, test_book, chapter_id=one.id)
        in_other_book = await suspended_flashcard(db_session, other_book)
        chapterless = await suspended_flashcard(db_session, test_book, created_at=T)
        in_two = await suspended_flashcard(db_session, test_book, chapter_id=two.id)
        in_one_later = await suspended_flashcard(
            db_session, test_book, chapter_id=one.id, created_at=T + timedelta(days=1)
        )
        in_one_earlier = await suspended_flashcard(
            db_session, test_book, chapter_id=one.id, created_at=T
        )

        assert await suspended_ids(client) == [
            in_one_earlier,
            in_one_later,
            in_two,
            chapterless,
            in_other_book,
        ]

    async def test_a_suspended_flashcard_carries_its_context_and_no_previews(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        chapter = await create_test_chapter(db_session, test_book, "Openings", chapter_number=1)
        await suspended_flashcard(db_session, test_book, chapter_id=chapter.id)

        (item,) = (await get_suspended(client)).json()["items"]

        assert context(item) == ("Test Book", "Openings", None, None)
        assert item["status"] == "suspended"
        assert "previews" not in item

    async def test_the_list_narrows_to_one_book_and_pages_with_its_total(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        other_book = await create_test_book(db_session, test_book.user_id, "Other Book")
        cards = [await suspended_flashcard(db_session, test_book) for _ in range(3)]
        await suspended_flashcard(db_session, other_book)

        page = (await get_suspended(client, book_id=test_book.id, limit=1, offset=1)).json()

        assert [item["id"] for item in page["items"]] == [cards[1]]
        assert (page["total"], page["offset"], page["limit"]) == (3, 1, 1)

    async def test_another_users_suspended_flashcards_never_appear(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        other_user: models.User,
    ) -> None:
        their_book = await create_test_book(db_session, other_user.id, "Their Book")
        await suspended_flashcard(db_session, their_book)
        mine = await suspended_flashcard(db_session, test_book)

        assert await suspended_ids(client) == [mine]
        response = await get_suspended(client, book_id=their_book.id)
        assert response.status_code == status.HTTP_404_NOT_FOUND
