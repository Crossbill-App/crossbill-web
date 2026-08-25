"""Tests for the ereader highlight pull endpoint."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Book, User
from tests.conftest import create_test_book, create_test_chapter, create_test_highlight


async def _upload(
    plugin_client: AsyncClient,
    client_book_id: str,
    highlights: list[dict[str, Any]],
    device_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {"client_book_id": client_book_id, "highlights": highlights}
    if device_id is not None:
        payload["device_id"] = device_id
    response = await plugin_client.post("/api/v1/highlights/sync", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["highlights_created"] == len(highlights)


@pytest.fixture
async def ereader_book(db_session: AsyncSession, test_user: User) -> Book:
    """A book identified by client_book_id."""
    return await create_test_book(
        db_session=db_session,
        user_id=test_user.id,
        title="Pullable Book",
        client_book_id="client-pull",
    )


async def test_returns_uploaded_highlights_with_device_fields(
    plugin_client: AsyncClient, ereader_book: Book
) -> None:
    await _upload(
        plugin_client,
        "client-pull",
        [
            {
                "text": "Placeable one",
                "page": 10,
                "datetime": "2024-01-15 14:30:22",
                "datetime_updated": "2024-01-16 09:05:00",
                "start_xpoint": "/body/div[1]/p[5]/text()[1].0",
                "end_xpoint": "/body/div[1]/p[5]/text()[1].42",
                "color": "yellow",
                "drawer": "lighten",
                "note": "Come back to this",
            },
            {
                "text": "No xpoints here",
                "page": 20,
                "datetime": "2024-01-15 15:00:00",
            },
        ],
        device_id="Kobo Clara",
    )

    response = await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["text"] for i in items] == ["Placeable one", "No xpoints here"]

    placeable, unplaceable = items
    # XPoint normalises the device's strings on store; the device gets those back.
    assert placeable["start_xpoint"] == "/body/DocFragment[1]/body/div[1]/p[5]"
    assert placeable["end_xpoint"] == "/body/DocFragment[1]/body/div[1]/p[5]/text().42"
    assert placeable["datetime"] == "2024-01-15 14:30:22"
    assert placeable["datetime_updated"] == "2024-01-16 09:05:00"
    assert placeable["page"] == 10
    assert placeable["note"] == "Come back to this"
    assert placeable["device_color"] == "yellow"
    assert placeable["device_style"] == "lighten"
    assert placeable["origin_device_id"] == "Kobo Clara"
    assert placeable["placeable"] is True

    assert unplaceable["start_xpoint"] is None
    assert unplaceable["end_xpoint"] is None
    assert unplaceable["note"] is None
    # Never edited on the device, so it has no edit time of its own.
    assert unplaceable["datetime_updated"] is None
    assert unplaceable["placeable"] is False


async def test_highlights_without_a_page_sort_last(
    plugin_client: AsyncClient, ereader_book: Book
) -> None:
    """Page orders the list; a device that sends none puts the highlight at the end."""
    await _upload(
        plugin_client,
        "client-pull",
        [
            {"text": "Pageless", "datetime": "2024-01-15 13:00:00"},
            {"text": "Page two", "page": 2, "datetime": "2024-01-15 14:00:00"},
            {"text": "Page one", "page": 1, "datetime": "2024-01-15 15:00:00"},
        ],
    )

    response = await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")

    assert response.status_code == 200
    assert [i["text"] for i in response.json()["items"]] == ["Page one", "Page two", "Pageless"]


async def test_soft_deleted_highlight_is_excluded(
    plugin_client: AsyncClient, ereader_book: Book
) -> None:
    await _upload(
        plugin_client,
        "client-pull",
        [
            {"text": "Kept", "page": 1, "datetime": "2024-01-15 14:00:00"},
            {"text": "Removed", "page": 2, "datetime": "2024-01-15 14:01:00"},
        ],
    )
    items = (await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")).json()[
        "items"
    ]
    doomed = next(i for i in items if i["text"] == "Removed")

    deletion = await plugin_client.request(
        "DELETE",
        f"/api/v1/books/{ereader_book.id}/highlight",
        json={"highlight_ids": [doomed["id"]]},
    )
    assert deletion.status_code == 200
    assert deletion.json()["deleted_count"] == 1

    response = await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")

    assert response.status_code == 200
    assert [i["text"] for i in response.json()["items"]] == ["Kept"]


async def test_unknown_client_book_id_returns_404(plugin_client: AsyncClient) -> None:
    response = await plugin_client.get("/api/v1/ereader/books/does-not-exist/highlights")

    assert response.status_code == 404


async def test_another_users_book_with_the_same_client_id_is_invisible(
    plugin_client: AsyncClient, db_session: AsyncSession, ereader_book: Book
) -> None:
    """Two devices can share a client_book_id; the highlights must not cross users."""
    other_user = User(email="other-pull@test.com")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    other_book = await create_test_book(
        db_session=db_session,
        user_id=other_user.id,
        title="Their Copy",
        client_book_id="client-pull",
    )
    await _upload(
        plugin_client, "client-pull", [{"text": "Mine", "datetime": "2024-01-15 14:00:00"}]
    )

    await create_test_highlight(
        db_session=db_session,
        book=other_book,
        user_id=other_user.id,
        text="Theirs",
        datetime_str="2024-01-15 14:00:00",
    )

    response = await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")

    assert response.status_code == 200
    assert [i["text"] for i in response.json()["items"]] == ["Mine"]


async def test_a_client_book_id_only_another_user_owns_is_a_404(
    plugin_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_user = User(email="stranger-pull@test.com")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    other_book = await create_test_book(
        db_session=db_session,
        user_id=other_user.id,
        title="Not Mine",
        client_book_id="client-theirs",
    )
    await create_test_highlight(
        db_session=db_session,
        book=other_book,
        user_id=other_user.id,
        text="Theirs",
        datetime_str="2024-01-15 14:00:00",
    )

    response = await plugin_client.get("/api/v1/ereader/books/client-theirs/highlights")

    assert response.status_code == 404


async def test_chapter_fields_come_from_the_books_chapters(
    plugin_client: AsyncClient, db_session: AsyncSession, ereader_book: Book
) -> None:
    await create_test_chapter(db_session, ereader_book, "The Opening", chapter_number=1)
    await _upload(
        plugin_client,
        "client-pull",
        [
            {
                "text": "In a chapter",
                "page": 1,
                "chapter": "The Opening",
                "chapter_number": 1,
                "datetime": "2024-01-15 14:00:00",
            },
            {"text": "Chapterless", "page": 2, "datetime": "2024-01-15 14:01:00"},
        ],
    )

    response = await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")

    assert response.status_code == 200
    in_chapter, chapterless = response.json()["items"]
    assert in_chapter["chapter_number"] == 1
    assert in_chapter["chapter_name"] == "The Opening"
    assert chapterless["chapter_number"] is None
    assert chapterless["chapter_name"] is None


async def test_book_without_highlights_returns_empty_list(
    plugin_client: AsyncClient, ereader_book: Book
) -> None:
    response = await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_highlight_removed_from_devices_is_excluded(
    db_session: AsyncSession, plugin_client: AsyncClient, ereader_book: Book, test_user: User
) -> None:
    """A highlight the user deleted on a device stays away from every device."""
    await create_test_highlight(
        db_session=db_session,
        book=ereader_book,
        user_id=test_user.id,
        text="Kept",
        datetime_str="2024-01-15 14:00:00",
        page=1,
    )
    await create_test_highlight(
        db_session=db_session,
        book=ereader_book,
        user_id=test_user.id,
        text="Deleted on the e-reader",
        datetime_str="2024-01-15 14:01:00",
        page=2,
        removed_from_devices_at=datetime(2024, 3, 1, tzinfo=UTC),
    )

    response = await plugin_client.get("/api/v1/ereader/books/client-pull/highlights")

    assert response.status_code == 200
    assert [i["text"] for i in response.json()["items"]] == ["Kept"]
