"""Tests for the 076 data migration that places existing books against their EPUBs.

The core runs against the same in-memory schema the API tests use, driven
through ``run_sync`` because the migration is synchronous, and every assertion
is against the stored row. The module is loaded from its path: ``alembic/versions``
is not a package.

The fixture book and its verified xpointers come from ``test_locator_ingest``,
which is where they were checked against ``minimal.epub``.
"""

import hashlib
import importlib.util
import logging
from collections.abc import Callable, Hashable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.anchors import Locator
from src.domain.common.value_objects.xpoint import XPoint, XPointRange
from src.infrastructure.web_reader.services import (
    xpoint_cfi_position_anchor_service as anchor_adapter,
)
from tests.conftest import (
    create_test_book,
    create_test_highlight,
    create_test_reading_session,
)
from tests.readium_helpers import fixture_bytes
from tests.test_locator_ingest import (
    FOUR_PLACEABLE,
    PLACEABLE_END,
    PLACEABLE_SELECTOR,
    PLACEABLE_START,
    PLACEABLE_TEXT,
    SESSION_END,
    SESSION_END_SELECTOR,
    SESSION_START,
    SESSION_START_SELECTOR,
    THREE_SPANS,
    UNPLACEABLE_END,
    UNPLACEABLE_START,
)

MINIMAL_EPUB = fixture_bytes("minimal")
MINIMAL_DIGEST = hashlib.sha256(MINIMAL_EPUB).hexdigest()
EPUB_FILE = "minimal-book.epub"

SESSION_START_TIME = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)


def _load_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "076_readium_rows_for_existing_books.py"
    )
    spec = importlib.util.spec_from_file_location("readium_backfill_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


async def run_backfill(db_session: AsyncSession, files: dict[str, bytes]) -> Any:  # noqa: ANN401
    """Run the migration core over ``files``, a file store keyed by EPUB file name."""
    connection = await db_session.connection()
    summary = await connection.run_sync(
        lambda sync_connection: migration.backfill_readium_rows(
            sync_connection, files.get, migration._app_code()
        )
    )
    await db_session.commit()
    return summary


async def run_migration(db_session: AsyncSession) -> Any:  # noqa: ANN401
    """Run ``upgrade``'s own entry point, which picks its app code and file store itself."""
    connection = await db_session.connection()
    result = await connection.run_sync(migration.run)
    await db_session.commit()
    return result


async def book_with_epub(
    db_session: AsyncSession, user_id: int, title: str, ebook_file: str | None = EPUB_FILE
) -> models.Book:
    book = await create_test_book(db_session=db_session, user_id=user_id, title=title)
    book.ebook_file = ebook_file
    await db_session.commit()
    await db_session.refresh(book)
    return book


async def xpointed_highlight(
    db_session: AsyncSession,
    book: models.Book,
    user_id: int,
    text: str = PLACEABLE_TEXT,
    start: str | None = PLACEABLE_START,
    end: str | None = PLACEABLE_END,
    deleted_at: datetime | None = None,
) -> models.Highlight:
    return await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=user_id,
        text=text,
        datetime_str="2024-01-15 14:30:22",
        start_xpoint=start,
        end_xpoint=end,
        deleted_at=deleted_at,
    )


async def xpointed_session(
    db_session: AsyncSession,
    book: models.Book,
    user_id: int,
    start: str = SESSION_START,
    end: str = SESSION_END,
    start_time: datetime = SESSION_START_TIME,
) -> models.ReadingSession:
    session = await create_test_reading_session(
        db_session=db_session, book=book, user_id=user_id, start_time=start_time
    )
    session.start_xpoint = start
    session.end_xpoint = end
    await db_session.commit()
    await db_session.refresh(session)
    return session


# The migration writes through the connection under the session, so an instance
# the test already holds keeps what it was loaded with unless the read says so.
FRESH = {"populate_existing": True}


async def stored_highlight(db_session: AsyncSession, highlight_id: int) -> models.Highlight:
    statement = select(models.Highlight).filter_by(id=highlight_id).execution_options(**FRESH)
    return (await db_session.execute(statement)).scalar_one()


async def stored_session(db_session: AsyncSession, session_id: int) -> models.ReadingSession:
    statement = select(models.ReadingSession).filter_by(id=session_id).execution_options(**FRESH)
    return (await db_session.execute(statement)).scalar_one()


async def stored_publication(
    db_session: AsyncSession, book_id: int
) -> models.BookPublication | None:
    statement = select(models.BookPublication).filter_by(book_id=book_id).execution_options(**FRESH)
    return (await db_session.execute(statement)).scalar_one_or_none()


@pytest.fixture
async def book(db_session: AsyncSession, test_user: models.User) -> models.Book:
    return await book_with_epub(db_session, test_user.id, "Placeable Book")


async def test_a_book_with_an_epub_gets_its_publication_index_and_its_locators(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    session = await xpointed_session(db_session, book, test_user.id)

    summary = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    publication = await stored_publication(db_session, book.id)
    assert publication is not None
    assert publication.file_name == EPUB_FILE
    assert publication.content_hash == MINIMAL_DIGEST
    assert [item["href"] for item in publication.publication["reading_order"]] == [
        "OEBPS/chapter1.xhtml",
        "OEBPS/chapter2.xhtml",
    ]
    assert publication.publication["metadata"]["title"] == "The Lantern Fixture"

    row = await stored_highlight(db_session, highlight.id)
    assert row.locator is not None
    assert row.locator["href"] == "OEBPS/chapter1.xhtml"
    assert row.locator["locations"]["cssSelector"] == PLACEABLE_SELECTOR
    assert row.locator["text"]["highlight"] == PLACEABLE_TEXT
    assert row.locator_confidence is None
    assert row.locator_source_hash == MINIMAL_DIGEST

    session_row = await stored_session(db_session, session.id)
    assert session_row.start_locator is not None
    assert session_row.start_locator["locations"]["cssSelector"] == SESSION_START_SELECTOR
    assert session_row.end_locator is not None
    assert session_row.end_locator["locations"]["cssSelector"] == SESSION_END_SELECTOR
    assert session_row.locator_source_hash == MINIMAL_DIGEST

    assert summary.books_seen == 1
    assert summary.publications_stored == 1
    assert summary.highlights_placed == 1
    assert summary.sessions_placed == 1
    assert summary.epubs_missing == 0
    assert summary.books_failed == 0


async def test_rows_derived_from_another_file_are_overwritten(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    highlight.locator_source_hash = "stale"
    db_session.add(
        models.BookPublication(
            book_id=book.id,
            file_name="older.epub",
            content_hash="stale",
            publication={"metadata": {}, "reading_order": [], "resources": [], "toc": []},
            derived_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    publication = await stored_publication(db_session, book.id)
    assert publication is not None
    assert publication.file_name == EPUB_FILE
    assert publication.content_hash == MINIMAL_DIGEST
    assert len(publication.publication["reading_order"]) == 2
    row = await stored_highlight(db_session, highlight.id)
    assert row.locator is not None
    assert row.locator["locations"]["cssSelector"] == PLACEABLE_SELECTOR
    assert row.locator_source_hash == MINIMAL_DIGEST


async def test_a_book_whose_epub_is_missing_is_skipped_and_the_run_carries_on(
    db_session: AsyncSession, test_user: models.User
) -> None:
    fileless = await book_with_epub(db_session, test_user.id, "Gone", "vanished.epub")
    lost = await xpointed_highlight(db_session, fileless, test_user.id)
    later = await book_with_epub(db_session, test_user.id, "Present")
    placed = await xpointed_highlight(db_session, later, test_user.id)

    summary = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    assert await stored_publication(db_session, fileless.id) is None
    untouched = await stored_highlight(db_session, lost.id)
    assert untouched.locator is None
    assert untouched.locator_source_hash is None
    assert await stored_publication(db_session, later.id) is not None
    assert (await stored_highlight(db_session, placed.id)).locator_source_hash == MINIMAL_DIGEST
    assert summary.books_seen == 2
    assert summary.epubs_missing == 1
    assert summary.books_failed == 0


async def test_a_book_whose_file_is_not_an_epub_is_counted_failed_and_left_alone(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    session = await xpointed_session(db_session, book, test_user.id)
    later = await book_with_epub(db_session, test_user.id, "Readable", "readable.epub")
    placed = await xpointed_highlight(db_session, later, test_user.id)

    summary = await run_backfill(
        db_session, {EPUB_FILE: b"not an epub", "readable.epub": MINIMAL_EPUB}
    )

    assert await stored_publication(db_session, book.id) is None
    row = await stored_highlight(db_session, highlight.id)
    assert row.locator is None
    assert row.locator_source_hash is None
    session_row = await stored_session(db_session, session.id)
    assert session_row.start_locator is None
    assert session_row.locator_source_hash is None
    assert (await stored_highlight(db_session, placed.id)).locator_source_hash == MINIMAL_DIGEST
    assert summary.books_failed == 1
    assert summary.publications_stored == 1


async def test_deleted_xpointless_malformed_and_fileless_rows_are_never_placed(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    deleted = await xpointed_highlight(
        db_session,
        book,
        test_user.id,
        text="Deleted but xpointed",
        deleted_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    xpointless = await xpointed_highlight(
        db_session, book, test_user.id, text="No xpoints at all", start=None, end=None
    )
    malformed = await xpointed_highlight(
        db_session, book, test_user.id, text="Malformed xpointer", start="garbage", end="garbage"
    )
    fileless_book = await book_with_epub(db_session, test_user.id, "No File", ebook_file=None)
    on_fileless = await xpointed_highlight(db_session, fileless_book, test_user.id)

    summary = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    for untouched_id in (deleted.id, xpointless.id, malformed.id, on_fileless.id):
        row = await stored_highlight(db_session, untouched_id)
        assert row.locator is None
        assert row.locator_source_hash is None
    assert summary.books_seen == 1
    assert summary.highlights_placed == 0


async def test_an_xpointer_this_epub_cannot_place_is_written_null_against_the_digest(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    # The digest without a locator is R4.3's staleness signal: this file was
    # tried and could not place the row, as against an absent hash, which says
    # nothing was tried.
    highlight = await xpointed_highlight(
        db_session,
        book,
        test_user.id,
        text="A passage of a chapter this book does not have",
        start=UNPLACEABLE_START,
        end=UNPLACEABLE_END,
    )
    session = await xpointed_session(
        db_session, book, test_user.id, start=UNPLACEABLE_START, end=UNPLACEABLE_END
    )

    summary = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    row = await stored_highlight(db_session, highlight.id)
    assert row.locator is None
    assert row.locator_source_hash == MINIMAL_DIGEST
    session_row = await stored_session(db_session, session.id)
    assert session_row.start_locator is None
    assert session_row.end_locator is None
    assert session_row.locator_source_hash == MINIMAL_DIGEST
    assert summary.highlights_placed == 0
    assert summary.sessions_placed == 0
    assert summary.books_failed == 0


async def test_each_book_is_derived_once_per_kind_however_many_rows_it_has(
    db_session: AsyncSession, test_user: models.User, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"ranges": 0, "points": 0}
    real_ranges = anchor_adapter.range_locators
    real_points = anchor_adapter.point_locators

    def counting_ranges[K: Hashable](
        epub_content: bytes, ranges: Mapping[K, XPointRange]
    ) -> dict[K, Locator | None]:
        calls["ranges"] += 1
        return real_ranges(epub_content, ranges)

    def counting_points[K: Hashable](
        epub_content: bytes, points: Mapping[K, XPoint]
    ) -> dict[K, Locator | None]:
        calls["points"] += 1
        return real_points(epub_content, points)

    # The migration imports these when it runs, so the adapter module is where a
    # stand-in has to sit for ``_app_code`` to pick it up.
    monkeypatch.setattr(anchor_adapter, "range_locators", counting_ranges)
    monkeypatch.setattr(anchor_adapter, "point_locators", counting_points)

    sessions: list[tuple[models.ReadingSession, str, str]] = []
    for title in ("First", "Second"):
        crowded = await book_with_epub(db_session, test_user.id, title)
        for text, start, end in FOUR_PLACEABLE[:3]:
            await xpointed_highlight(db_session, crowded, test_user.id, text, start, end)
        for index, (_, start, end, start_selector, end_selector) in enumerate(THREE_SPANS[:2]):
            session = await xpointed_session(
                db_session,
                crowded,
                test_user.id,
                start=start,
                end=end,
                start_time=datetime(2024, 1, 15 + index, 10, 0, tzinfo=UTC),
            )
            sessions.append((session, start_selector, end_selector))

    summary = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    assert calls == {"ranges": 2, "points": 2}
    assert summary.highlights_placed == 6
    assert summary.sessions_placed == 4
    for session, start_selector, end_selector in sessions:
        row = await stored_session(db_session, session.id)
        assert row.start_locator is not None
        assert row.start_locator["locations"]["cssSelector"] == start_selector
        assert row.end_locator is not None
        assert row.end_locator["locations"]["cssSelector"] == end_selector


async def test_another_users_highlight_on_the_same_book_is_placed_too(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    """The backfill is keyed by file, not by owner: both readers' rows point at it."""
    stranger = models.User(email="stranger-backfill@test.com", hashed_password="x")
    db_session.add(stranger)
    await db_session.commit()
    mine = await xpointed_highlight(db_session, book, test_user.id)
    theirs = await xpointed_highlight(
        db_session, book, stranger.id, text="Nothing else in the house moved"
    )

    await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    assert (await stored_highlight(db_session, mine.id)).locator_source_hash == MINIMAL_DIGEST
    row = await stored_highlight(db_session, theirs.id)
    assert row.user_id == stranger.id
    assert row.locator is not None
    assert row.locator["locations"]["cssSelector"] == PLACEABLE_SELECTOR
    assert row.locator_source_hash == MINIMAL_DIGEST


SKIP_LOGGER = "alembic.readium_backfill"

# Each is a name on the migration module and what a refactor of the app code, or
# a deployment the migration cannot read, makes calling it do.
BROKEN = {
    "an import the application no longer answers": ("_app_code", ImportError("renamed")),
    "an attribute a refactor moved": ("_app_code", AttributeError("moved")),
    "a file store that cannot be built": ("_epub_reader", RuntimeError("no bucket")),
}


def raising(failure: Exception) -> Callable[..., Any]:
    def raise_it(*_args: object, **_kwargs: object) -> Any:  # noqa: ANN401
        raise failure

    return raise_it


async def assert_nothing_was_derived(
    db_session: AsyncSession, book: models.Book, highlight: models.Highlight
) -> None:
    row = await stored_highlight(db_session, highlight.id)
    assert row.locator is None
    assert row.locator_source_hash is None
    assert await stored_publication(db_session, book.id) is None


def assert_one_skip_logged(caplog: pytest.LogCaptureFixture) -> None:
    records = [record for record in caplog.records if record.name == SKIP_LOGGER]
    assert len(records) == 1
    assert "skipped" in records[0].getMessage()
    assert records[0].levelno >= logging.WARNING


@pytest.mark.parametrize(("attribute", "failure"), BROKEN.values(), ids=BROKEN.keys())
async def test_a_failure_before_the_first_book_skips_the_run_and_leaves_every_row_alone(
    db_session: AsyncSession,
    test_user: models.User,
    book: models.Book,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    attribute: str,
    failure: Exception,
) -> None:
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    monkeypatch.setattr(migration, attribute, raising(failure))

    with caplog.at_level(logging.WARNING, logger=SKIP_LOGGER):
        assert await run_migration(db_session) is None

    await assert_nothing_was_derived(db_session, book, highlight)
    assert_one_skip_logged(caplog)


async def test_a_database_error_partway_takes_back_what_the_run_had_written(
    db_session: AsyncSession,
    test_user: models.User,
    book: models.Book,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The first book is derived in full before the second one faults, so what the
    # savepoint rolls back is a run that had already written rows.
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    await book_with_epub(db_session, test_user.id, "Faulting", "faulting.epub")
    running: list[sa.Connection] = []

    def read_epub(file_name: str) -> bytes | None:
        if file_name == "faulting.epub":
            running[0].execute(sa.text("SELECT * FROM no_such_table"))
        return MINIMAL_EPUB

    monkeypatch.setattr(migration, "_epub_reader", lambda: read_epub)

    def run_recording_the_connection(sync_connection: sa.Connection) -> Any:  # noqa: ANN401
        running.append(sync_connection)
        return migration.run(sync_connection)

    with caplog.at_level(logging.WARNING, logger=SKIP_LOGGER):
        assert await (await db_session.connection()).run_sync(run_recording_the_connection) is None
    await db_session.commit()

    await assert_nothing_was_derived(db_session, book, highlight)
    assert_one_skip_logged(caplog)


async def test_a_database_error_inside_a_book_ends_the_run_rather_than_the_book(
    db_session: AsyncSession,
    test_user: models.User,
    book: models.Book,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Two books: were the failing statement contained per book, the second would
    # still be derived, the run would finish, and the log would say so.
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    second = await book_with_epub(db_session, test_user.id, "Second", "second.epub")
    on_second = await xpointed_highlight(db_session, second, test_user.id)

    def store_publication(connection: sa.Connection, *_: object) -> None:
        connection.execute(sa.text("SELECT * FROM no_such_table"))

    monkeypatch.setattr(migration, "_store_publication", store_publication)
    monkeypatch.setattr(
        migration,
        "_epub_reader",
        lambda: {EPUB_FILE: MINIMAL_EPUB, "second.epub": MINIMAL_EPUB}.get,
    )

    with caplog.at_level(logging.WARNING, logger=SKIP_LOGGER):
        assert await (await db_session.connection()).run_sync(migration.run) is None
    await db_session.commit()

    await assert_nothing_was_derived(db_session, book, highlight)
    await assert_nothing_was_derived(db_session, second, on_second)
    assert_one_skip_logged(caplog)


def test_no_application_code_is_imported_at_module_level() -> None:
    # Alembic imports every file under ``versions`` to build its revision graph.
    imported_from_app = [
        name
        for name, value in vars(migration).items()
        if str(getattr(value, "__module__", "") or "").startswith("src")
    ]
    assert imported_from_app == []
