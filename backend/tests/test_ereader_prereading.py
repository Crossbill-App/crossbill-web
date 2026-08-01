"""Tests for the ereader book prereading endpoint."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Book, Chapter
from src.models import ChapterPrereadingContent as PrereadingContentORM
from tests.conftest import create_test_book, create_test_chapter


async def _add_prereading(
    db_session: AsyncSession,
    chapter: Chapter,
    summary: str = "A summary",
    keypoints: list[str] | None = None,
    questions: list[dict[str, str]] | None = None,
) -> PrereadingContentORM:
    content = PrereadingContentORM(
        chapter_id=chapter.id,
        summary=summary,
        keypoints=keypoints or ["Keypoint 1"],
        questions=questions
        or [{"question": "What is X?", "answer": "It is Y.", "user_answer": "My guess"}],
        generated_at=datetime(2026, 7, 1, tzinfo=UTC),
        ai_model="test-model",
    )
    db_session.add(content)
    await db_session.commit()
    await db_session.refresh(content)
    return content


@pytest.fixture
async def prereading_book(db_session: AsyncSession, test_user: Book) -> Book:
    """A book identified by client_book_id."""
    return await create_test_book(
        db_session=db_session,
        user_id=test_user.id,
        title="Prereading Book",
        client_book_id="client-abc",
    )


async def test_returns_items_ordered_by_chapter_number(
    client: AsyncClient, db_session: AsyncSession, prereading_book: Book
) -> None:
    parent = await create_test_chapter(db_session, prereading_book, "Topic 1", chapter_number=1)
    ch_a = await create_test_chapter(
        db_session, prereading_book, "Exercises", chapter_number=7, parent_id=parent.id
    )
    ch_b = await create_test_chapter(
        db_session, prereading_book, "Intro", chapter_number=2, parent_id=parent.id
    )
    await _add_prereading(db_session, ch_a, summary="Exercises summary")
    await _add_prereading(db_session, ch_b, summary="Intro summary")

    response = await client.get("/api/v1/ereader/books/client-abc/prereading")

    assert response.status_code == 200
    items = response.json()["items"]
    # Ordered by chapter_number ascending: Intro (2) before Exercises (7).
    assert [i["chapter_number"] for i in items] == [2, 7]
    assert items[0]["chapter_name"] == "Intro"
    assert items[0]["parent_chapter_name"] == "Topic 1"
    assert items[1]["chapter_name"] == "Exercises"
    assert items[1]["summary"] == "Exercises summary"


async def test_duplicate_chapter_names_disambiguated_by_parent(
    client: AsyncClient, db_session: AsyncSession, prereading_book: Book
) -> None:
    topic1 = await create_test_chapter(db_session, prereading_book, "Topic 1", chapter_number=1)
    topic2 = await create_test_chapter(db_session, prereading_book, "Topic 2", chapter_number=2)
    ex1 = await create_test_chapter(
        db_session, prereading_book, "Exercises", chapter_number=3, parent_id=topic1.id
    )
    ex2 = await create_test_chapter(
        db_session, prereading_book, "Exercises", chapter_number=4, parent_id=topic2.id
    )
    await _add_prereading(db_session, ex1)
    await _add_prereading(db_session, ex2)

    response = await client.get("/api/v1/ereader/books/client-abc/prereading")

    assert response.status_code == 200
    items = response.json()["items"]
    exercise_items = [i for i in items if i["chapter_name"] == "Exercises"]
    assert len(exercise_items) == 2
    parent_names = {i["parent_chapter_name"] for i in exercise_items}
    assert parent_names == {"Topic 1", "Topic 2"}


async def test_root_chapter_has_null_parent_name(
    client: AsyncClient, db_session: AsyncSession, prereading_book: Book
) -> None:
    root = await create_test_chapter(db_session, prereading_book, "Root Chapter", chapter_number=1)
    await _add_prereading(db_session, root)

    response = await client.get("/api/v1/ereader/books/client-abc/prereading")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["parent_chapter_name"] is None


async def test_chapters_without_prereading_are_omitted(
    client: AsyncClient, db_session: AsyncSession, prereading_book: Book
) -> None:
    ch_with = await create_test_chapter(
        db_session, prereading_book, "Has prereading", chapter_number=1
    )
    await create_test_chapter(db_session, prereading_book, "No prereading", chapter_number=2)
    await _add_prereading(db_session, ch_with)

    response = await client.get("/api/v1/ereader/books/client-abc/prereading")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["chapter_name"] == "Has prereading"


async def test_book_with_zero_prereading_returns_empty_list(
    client: AsyncClient, db_session: AsyncSession, prereading_book: Book
) -> None:
    await create_test_chapter(db_session, prereading_book, "Lonely chapter", chapter_number=1)

    response = await client.get("/api/v1/ereader/books/client-abc/prereading")

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_unknown_client_book_id_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ereader/books/does-not-exist/prereading")

    assert response.status_code == 404


async def test_questions_contain_only_question_strings(
    client: AsyncClient, db_session: AsyncSession, prereading_book: Book
) -> None:
    chapter = await create_test_chapter(db_session, prereading_book, "Chapter", chapter_number=1)
    await _add_prereading(
        db_session,
        chapter,
        questions=[
            {
                "question": "What is the capital?",
                "answer": "Secret AI answer",
                "user_answer": "Secret user answer",
            }
        ],
    )

    response = await client.get("/api/v1/ereader/books/client-abc/prereading")

    assert response.status_code == 200
    questions = response.json()["items"][0]["questions"]
    assert questions == ["What is the capital?"]
    body = response.text
    assert "Secret AI answer" not in body
    assert "Secret user answer" not in body
