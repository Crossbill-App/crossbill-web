"""Tests for Flashcard Reviews, suspending cards, and the queue of Due Cards."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.domain.common.time import as_aware
from src.infrastructure.learning.services.fsrs_review_scheduler import FsrsReviewScheduler
from src.infrastructure.reading.routers.reader_clock import reader_now
from src.main import app
from tests.conftest import create_test_book, create_test_chapter, create_test_highlight

T = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def unfuzzed_scheduler() -> Iterator[None]:
    """Schedule without fuzz, so a due date is the one FSRS computes."""
    from src.core import container  # noqa: PLC0415

    container.shared.review_scheduler.override(FsrsReviewScheduler(enable_fuzzing=False))
    yield
    container.shared.review_scheduler.reset_override()


async def record_review(
    client: AsyncClient, flashcard_id: int, rating: str, reviewed_at: datetime
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/flashcards/{flashcard_id}/reviews",
        json={"rating": rating, "reviewed_at": reviewed_at.isoformat()},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def create_flashcard(
    db_session: AsyncSession, book: models.Book, **fields: object
) -> models.Flashcard:
    flashcard = models.Flashcard(
        user_id=book.user_id, book_id=book.id, question="Q", answer="A", **fields
    )
    db_session.add(flashcard)
    await db_session.commit()
    await db_session.refresh(flashcard)
    return flashcard


def at(value: object) -> datetime:
    """Read a timestamp from a response; SQLite hands them back without a zone."""
    assert isinstance(value, str)
    return as_aware(datetime.fromisoformat(value))


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
        in_order = await create_flashcard(db_session, test_book)
        late = await create_flashcard(db_session, test_book)
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

    async def test_a_review_needs_a_timezone(
        self, client: AsyncClient, test_flashcard: models.Flashcard
    ) -> None:
        response = await client.post(
            f"/api/v1/flashcards/{test_flashcard.id}/reviews",
            json={"rating": "good", "reviewed_at": "2026-11-01T09:00:00"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_another_users_card_cannot_be_reviewed(
        self, client: AsyncClient, db_session: AsyncSession, other_user: models.User
    ) -> None:
        their_book = await create_test_book(db_session, other_user.id, "Their Book")
        their_card = await create_flashcard(db_session, their_book)

        response = await client.post(
            f"/api/v1/flashcards/{their_card.id}/reviews",
            json={"rating": "good", "reviewed_at": T.isoformat()},
        )

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

        response = await client.post(
            f"/api/v1/flashcards/{test_flashcard.id}/reviews",
            json={"rating": "good", "reviewed_at": T.isoformat()},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        unsuspended = await set_status(client, test_flashcard.id, "active")
        assert unsuspended["last_review"] is None

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
        self, client: AsyncClient, db_session: AsyncSession, other_user: models.User
    ) -> None:
        their_book = await create_test_book(db_session, other_user.id, "Their Book")
        their_card = await create_flashcard(db_session, their_book)

        response = await client.put(
            f"/api/v1/flashcards/{their_card.id}/status", json={"status": "suspended"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


NOW = T + timedelta(days=10)


@pytest.fixture
def pinned_now(client: AsyncClient) -> None:
    """Pin ``reader_now``. Depends on ``client``, whose teardown clears the overrides."""
    app.dependency_overrides[reader_now] = lambda: NOW


async def due_ids(client: AsyncClient, **params: int) -> list[int]:
    response = await client.get("/api/v1/flashcards/due", params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return [item["id"] for item in response.json()["items"]]


@pytest.mark.usefixtures("pinned_now")
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
        long_overdue = await create_flashcard(db_session, test_book)
        just_forgotten = await create_flashcard(db_session, test_book)
        await record_review(client, long_overdue.id, "good", T)
        await record_review(client, just_forgotten.id, "again", NOW - timedelta(days=1))
        chapterless = await create_flashcard(
            db_session, test_book, created_at=T - timedelta(days=5)
        )
        in_chapter_two = await create_flashcard(
            db_session, test_book, chapter_id=chapter_two.id, created_at=T - timedelta(days=4)
        )
        via_highlight = await create_flashcard(
            db_session, test_book, highlight_id=highlight.id, created_at=T - timedelta(days=2)
        )
        in_chapter_one = await create_flashcard(
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

    async def test_cards_not_yet_due_and_suspended_cards_stay_out(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        due = await create_flashcard(db_session, test_book)
        not_yet_due = await create_flashcard(db_session, test_book)
        suspended = await create_flashcard(db_session, test_book)
        suspended_due = await create_flashcard(db_session, test_book)
        await record_review(client, due.id, "good", T)
        await record_review(client, not_yet_due.id, "good", NOW - timedelta(days=1))
        await record_review(client, suspended_due.id, "good", T)
        await set_status(client, suspended.id, "suspended")
        await set_status(client, suspended_due.id, "suspended")

        assert await due_ids(client) == [due.id]

    async def test_the_queue_narrows_to_one_book(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        other_book = await create_test_book(db_session, test_book.user_id, "Other Book")
        in_book = await create_flashcard(db_session, test_book)
        await create_flashcard(db_session, other_book)

        assert await due_ids(client, book_id=test_book.id) == [in_book.id]

    async def test_the_queue_pages_with_its_full_total(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        cards = [await create_flashcard(db_session, test_book) for _ in range(3)]

        response = await client.get("/api/v1/flashcards/due", params={"limit": 1, "offset": 1})

        page = response.json()
        assert [item["id"] for item in page["items"]] == [cards[1].id]
        assert (page["total"], page["offset"], page["limit"]) == (3, 1, 1)

    async def test_another_users_cards_never_appear(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        other_user: models.User,
    ) -> None:
        their_book = await create_test_book(db_session, other_user.id, "Their Book")
        await create_flashcard(db_session, their_book)
        mine = await create_flashcard(db_session, test_book)

        assert await due_ids(client) == [mine.id]
        response = await client.get("/api/v1/flashcards/due", params={"book_id": their_book.id})
        assert response.status_code == status.HTTP_404_NOT_FOUND
