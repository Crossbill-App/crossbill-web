"""The plugin's old ``/upload`` paths, kept until no plugin calls them.

Both endpoints answer under ``/sync`` now; these aliases exist only so plugins
released before the rename keep syncing. Delete this file with them.
"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from tests.conftest import CreateBookFunc

CLIENT_BOOK_ID = "alias-book"


async def test_highlights_upload_alias_stores_highlights(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    create_book_via_api: CreateBookFunc,
) -> None:
    await create_book_via_api({"client_book_id": CLIENT_BOOK_ID, "title": "Alias Book"})

    response = await plugin_client.post(
        "/api/v1/highlights/upload",
        json={
            "client_book_id": CLIENT_BOOK_ID,
            "highlights": [
                {
                    "text": "A sentence worth keeping",
                    "datetime": "2026-01-15 14:30:22",
                }
            ],
        },
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["highlights_created"] == 1

    stored = await db_session.execute(select(models.Highlight))
    assert [highlight.text for highlight in stored.scalars().all()] == ["A sentence worth keeping"]


async def test_reading_sessions_upload_alias_stores_sessions(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    create_book_via_api: CreateBookFunc,
) -> None:
    await create_book_via_api({"client_book_id": CLIENT_BOOK_ID, "title": "Alias Book"})

    response = await plugin_client.post(
        "/api/v1/reading_sessions/upload",
        json={
            "client_book_id": CLIENT_BOOK_ID,
            "sessions": [
                {
                    "start_time": "2026-01-15T10:00:00Z",
                    "end_time": "2026-01-15T11:00:00Z",
                    "device_id": "kobo-1",
                    "start_page": 10,
                    "end_page": 15,
                }
            ],
        },
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["created_count"] == 1

    stored = await db_session.execute(select(models.ReadingSession))
    assert [session.device_id for session in stored.scalars().all()] == ["kobo-1"]
