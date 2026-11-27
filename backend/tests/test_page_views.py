"""Page Views synced from KOReader inside each session of ``/reading_sessions/sync``.

The fixture book is ``minimal.epub``. ``reading_session`` spans 10:00 to 11:00
on 2024-01-15, and every Page View below is placed against that span.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.config import get_settings
from tests.test_locator_ingest import (
    MINIMAL_EPUB_DIGEST,
    UNPLACEABLE_START,
    reading_session,
    sync_sessions,
    upload_epub,
)

CH1_P1 = "/body/DocFragment[1]/body/div/p[1]/text().0"
CH1_P3_END = "/body/DocFragment[1]/body/div/p[3]/text().32"
CH1_P4 = "/body/DocFragment[1]/body/div/p[4]/text().10"
CH2_P1 = "/body/DocFragment[2]/body/div/p[1]/text().5"


def page_view(
    start_xpoint: str, end_xpoint: str, shown_at: str, duration_seconds: int
) -> dict[str, Any]:
    return {
        "start_xpoint": start_xpoint,
        "end_xpoint": end_xpoint,
        "shown_at": f"2024-01-15T{shown_at}Z",
        "duration_seconds": duration_seconds,
    }


def session_with(device_id: str, *page_views: dict[str, Any]) -> dict[str, Any]:
    return {**reading_session(device_id), "page_views": list(page_views)}


@pytest.fixture
async def book_id(plugin_client: AsyncClient, storage_dir: Path) -> int:
    return await upload_epub(plugin_client)


async def stored_page_views(db_session: AsyncSession) -> list[models.PageView]:
    db_session.expire_all()
    result = await db_session.scalars(select(models.PageView).order_by(models.PageView.shown_at))
    return list(result.all())


async def session_id_of(db_session: AsyncSession, device_id: str) -> int:
    return await db_session.scalar(
        select(models.ReadingSession.id).filter_by(device_id=device_id)
    ) or pytest.fail(f"no session from {device_id}")


async def test_a_synced_page_view_is_stored_with_its_positions_and_offsets(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    response = await sync_sessions(
        plugin_client,
        [session_with("kobo-1", page_view(CH1_P1, CH1_P3_END, "10:05:00", 42))],
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1
    [stored] = await stored_page_views(db_session)
    assert stored.reading_session_id == await session_id_of(db_session, "kobo-1")
    assert (stored.start_xpoint, stored.end_xpoint) == (CH1_P1, CH1_P3_END)
    assert (stored.start_position, stored.end_position) == ([6, 0], [9, 32])
    assert (stored.start_offset, stored.end_offset) == (11, 135)
    assert stored.position_source_hash == MINIMAL_EPUB_DIGEST
    assert stored.shown_at.replace(tzinfo=UTC) == datetime(2024, 1, 15, 10, 5, tzinfo=UTC)
    assert stored.duration_ms == 42_000


async def test_a_sync_without_page_views_stores_the_session_alone(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    response = await sync_sessions(plugin_client, [reading_session("kobo-1")])

    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": True,
        "message": "Created 1 session.",
        "book_id": book_id,
        "created_count": 1,
        "skipped_duplicate_count": 0,
    }
    await session_id_of(db_session, "kobo-1")
    assert await stored_page_views(db_session) == []


async def test_page_views_outside_the_span_or_the_book_are_dropped_and_the_sync_succeeds(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    response = await sync_sessions(
        plugin_client,
        [
            session_with(
                "kobo-1",
                page_view(CH1_P1, CH1_P3_END, "09:59:57", 30),
                page_view(CH1_P1, CH1_P3_END, "09:59:58", 30),
                page_view(CH1_P3_END, CH1_P4, "10:20:00", 30),
                page_view(UNPLACEABLE_START, CH1_P4, "10:30:00", 30),
                page_view(CH1_P4, CH2_P1, "10:59:30", 32),
                page_view(CH1_P4, CH2_P1, "10:59:30", 33),
                page_view(CH1_P4, CH1_P1, "10:40:00", 30),
                page_view(CH1_P1, CH1_P3_END, "10:41:00", -5),
                page_view(CH1_P1, CH1_P3_END, "10:42:00", 10**12),
                page_view(CH1_P1, CH1_P3_END, "10:43:00", 10**15),
            )
        ],
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1
    assert [
        (p.shown_at.replace(tzinfo=UTC).strftime("%H:%M:%S"), p.duration_ms)
        for p in await stored_page_views(db_session)
    ] == [("09:59:58", 30_000), ("10:20:00", 30_000), ("10:59:30", 32_000)]


async def test_a_session_sent_twice_in_one_sync_keeps_the_first_ones_page_views(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    response = await sync_sessions(
        plugin_client,
        [
            session_with("kobo-1", page_view(CH1_P1, CH1_P3_END, "10:05:00", 42)),
            session_with("kobo-1", page_view(CH1_P3_END, CH1_P4, "10:06:00", 20)),
        ],
    )

    assert response.status_code == 200, response.text
    assert [p.duration_ms for p in await stored_page_views(db_session)] == [42_000]


async def test_a_session_too_short_to_store_takes_its_page_views_with_it(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    start = datetime(2024, 1, 15, 10, tzinfo=UTC)
    too_short = timedelta(seconds=get_settings().MINIMUM_READING_SESSION_DURATION - 1)
    short = {
        **session_with("kobo-1", page_view(CH1_P1, CH1_P3_END, "10:00:00", 1)),
        "end_time": (start + too_short).isoformat(),
    }

    response = await sync_sessions(plugin_client, [short])

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 0
    assert await stored_page_views(db_session) == []


async def test_a_resynced_session_adds_no_page_views(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    first = page_view(CH1_P1, CH1_P3_END, "10:05:00", 42)
    await sync_sessions(plugin_client, [session_with("kobo-1", first)])

    response = await sync_sessions(
        plugin_client,
        [
            session_with("kobo-1", first, page_view(CH1_P3_END, CH1_P4, "10:06:00", 20)),
            session_with("kobo-2", page_view(CH1_P4, CH2_P1, "10:07:00", 25)),
        ],
    )

    assert response.status_code == 200, response.text
    assert response.json()["skipped_duplicate_count"] == 1
    assert [(p.reading_session_id, p.duration_ms) for p in await stored_page_views(db_session)] == [
        (await session_id_of(db_session, "kobo-1"), 42_000),
        (await session_id_of(db_session, "kobo-2"), 25_000),
    ]


async def test_deleting_the_book_removes_its_page_views(
    plugin_client: AsyncClient, client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    await sync_sessions(
        plugin_client, [session_with("kobo-1", page_view(CH1_P1, CH1_P3_END, "10:05:00", 42))]
    )
    assert len(await stored_page_views(db_session)) == 1

    response = await client.delete(f"/api/v1/books/{book_id}")

    assert response.status_code == 204, response.text
    assert await stored_page_views(db_session) == []
