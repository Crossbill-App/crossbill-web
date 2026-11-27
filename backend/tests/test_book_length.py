"""The character offsets a book's chapters start at, and the book's character total.

An upload measures them from the EPUB. A book stored before they existed has
neither, and the next session sync or web reader position measures it instead,
from the index that request builds anyway.

``minimal.epub`` holds chapter one's 182 characters and chapter two's 90.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.readium_helpers import fixture_bytes
from tests.test_locator_ingest import CLIENT_BOOK_ID, reading_session, sync_sessions
from tests.test_readium_reading_position import CH1_HREF, CH1_QUOTE, locator, write

MEASURED = (272, {"Chapter One": 0, "Chapter Two": 182})


@pytest.fixture
async def book_id(plugin_client: AsyncClient, storage_dir: Path) -> int:
    response = await plugin_client.post(
        "/api/v1/ereader/books",
        files={"epub": ("book.epub", fixture_bytes("minimal"), "application/epub+zip")},
        data={"client_book_id": CLIENT_BOOK_ID},
    )
    assert response.status_code == 200, response.text
    return response.json()["book_id"]


async def measurements(
    db_session: AsyncSession, book_id: int
) -> tuple[int | None, dict[str, int | None]]:
    book = await db_session.scalar(
        select(models.Book).filter_by(id=book_id).execution_options(populate_existing=True)
    )
    assert book is not None
    chapters = await db_session.scalars(
        select(models.Chapter).filter_by(book_id=book_id).execution_options(populate_existing=True)
    )
    return book.total_characters, {chapter.name: chapter.start_offset for chapter in chapters}


async def store_measurements(
    db_session: AsyncSession, book_id: int, total: int | None, start_offset: int | None
) -> None:
    await db_session.execute(
        update(models.Book).filter_by(id=book_id).values(total_characters=total)
    )
    await db_session.execute(
        update(models.Chapter).filter_by(book_id=book_id).values(start_offset=start_offset)
    )
    await db_session.commit()


async def test_an_uploaded_epub_measures_the_book_and_its_chapters(
    db_session: AsyncSession, book_id: int
) -> None:
    assert await measurements(db_session, book_id) == MEASURED


async def test_a_session_sync_measures_a_book_stored_before_offsets(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    await store_measurements(db_session, book_id, total=None, start_offset=None)

    response = await sync_sessions(plugin_client, [reading_session("kobo-1")])

    assert response.status_code == 200, response.text
    assert await measurements(db_session, book_id) == MEASURED


async def test_a_later_sync_leaves_a_measured_book_alone(
    plugin_client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    await store_measurements(db_session, book_id, total=1, start_offset=7)

    response = await sync_sessions(plugin_client, [reading_session("kobo-1")])

    assert response.status_code == 200, response.text
    assert await measurements(db_session, book_id) == (1, {"Chapter One": 7, "Chapter Two": 7})


async def test_a_web_reader_position_measures_a_book_stored_before_offsets(
    client: AsyncClient, db_session: AsyncSession, book_id: int
) -> None:
    await store_measurements(db_session, book_id, total=None, start_offset=None)
    book = await db_session.get_one(models.Book, book_id)

    response = await write(client, book, locator(CH1_HREF, quote=CH1_QUOTE))

    assert response.status_code == 200, response.text
    assert await measurements(db_session, book_id) == MEASURED
