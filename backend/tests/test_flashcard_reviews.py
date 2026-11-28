"""Tests for recording Flashcard Reviews and the state they schedule."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.domain.common.time import as_aware
from src.infrastructure.learning.services.fsrs_review_scheduler import FsrsReviewScheduler
from tests.conftest import create_test_book

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
