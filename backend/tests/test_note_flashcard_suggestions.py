"""Tests for GET /notes/{note_id}/flashcard_suggestions."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.models import AIUsageRecord, Book, Highlight, Note, User
from tests.ai_helpers import FakeAgent
from tests.conftest import create_test_book, create_test_highlight

OTHER_USER_ID = 2


async def plant_note(db: AsyncSession, book: Book, title: str, body: str = "") -> Note:
    note = Note(user_id=book.user_id, title=title, body=body, books=[book])
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def plant_highlight(
    db: AsyncSession, book: Book, text: str, *, deleted: bool = False
) -> Highlight:
    return await create_test_highlight(
        db,
        book,
        book.user_id,
        text=text,
        datetime_str="2024-01-15 14:30:22",
        deleted_at=datetime.now(UTC) if deleted else None,
    )


async def link(db: AsyncSession, note: Note, *highlights: Highlight) -> None:
    note.highlights = list(highlights)
    await db.commit()


async def suggest(client: AsyncClient, note: Note) -> list[dict[str, str]]:
    response = await client.get(f"/api/v1/notes/{note.id}/flashcard_suggestions")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["items"]


async def test_returns_the_models_suggestions(
    client: AsyncClient,
    db_session: AsyncSession,
    test_book: Book,
    ai_enabled: None,
    flashcard_agent: FakeAgent,
) -> None:
    note = await plant_note(db_session, test_book, "Raskolnikov")

    items = await suggest(client, note)

    assert items == [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]


async def test_prompts_with_title_body_and_live_linked_highlights(
    client: AsyncClient,
    db_session: AsyncSession,
    test_book: Book,
    ai_enabled: None,
    flashcard_agent: FakeAgent,
) -> None:
    note = await plant_note(db_session, test_book, "Raskolnikov", "The novel's protagonist.")
    first = await plant_highlight(db_session, test_book, "First highlight text")
    deleted = await plant_highlight(db_session, test_book, "Deleted highlight", deleted=True)
    second = await plant_highlight(db_session, test_book, "Second highlight text")
    await link(db_session, note, first, deleted, second)

    await suggest(client, note)

    assert flashcard_agent.received_prompts == [
        "Raskolnikov\n\nThe novel's protagonist.\n\nFirst highlight text\n\nSecond highlight text"
    ]


async def test_skips_a_linked_highlight_the_user_cannot_see(
    client: AsyncClient,
    db_session: AsyncSession,
    test_book: Book,
    ai_enabled: None,
    flashcard_agent: FakeAgent,
) -> None:
    db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
    await db_session.commit()
    other_book = await create_test_book(db_session, OTHER_USER_ID, title="Private Book")
    foreign = await plant_highlight(db_session, other_book, "Someone else's highlight")
    note = await plant_note(db_session, test_book, "Raskolnikov")
    await link(db_session, note, foreign)

    await suggest(client, note)

    assert flashcard_agent.received_prompts == ["Raskolnikov"]


async def test_a_blank_body_is_left_out_of_the_prompt(
    client: AsyncClient,
    db_session: AsyncSession,
    test_book: Book,
    ai_enabled: None,
    flashcard_agent: FakeAgent,
) -> None:
    note = await plant_note(db_session, test_book, "Raskolnikov", "   ")

    await suggest(client, note)

    assert flashcard_agent.received_prompts == ["Raskolnikov"]


async def test_records_usage_against_the_note(
    client: AsyncClient,
    db_session: AsyncSession,
    test_book: Book,
    ai_enabled: None,
    flashcard_agent: FakeAgent,
) -> None:
    note = await plant_note(db_session, test_book, "Raskolnikov")

    await suggest(client, note)

    record = (await db_session.execute(select(AIUsageRecord))).scalar_one()
    assert (record.user_id, record.task_type, record.entity_type, record.entity_id) == (
        test_book.user_id,
        "flashcard_suggestions",
        "note",
        note.id,
    )


async def test_returns_404_for_another_users_note(
    client: AsyncClient, db_session: AsyncSession, ai_enabled: None, flashcard_agent: FakeAgent
) -> None:
    db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
    await db_session.commit()
    other_book = await create_test_book(db_session, OTHER_USER_ID, title="Private Book")
    note = await plant_note(db_session, other_book, "Private")

    response = await client.get(f"/api/v1/notes/{note.id}/flashcard_suggestions")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert flashcard_agent.received_prompts == []
