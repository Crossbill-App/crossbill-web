"""Tests for the one-off backfill that gives existing books their Readium rows.

There is no endpoint -- migration 076 is the only caller -- so the use case is
built on the API tests' own in-memory schema with the real repositories, the
real EPUB parser and the real anchor service, and only the file store is faked.
Every assertion is against the stored row.

The fixture book and its verified xpointers come from ``test_locator_ingest``,
which is where they were checked against ``minimal.epub``.
"""

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.commands.backfill_book_locators_use_case import (
    BackfillBookLocatorsUseCase,
)
from src.application.web_reader.commands.backfill_readium_rows_use_case import (
    BackfillReadiumRowsUseCase,
    ReadiumBackfillReport,
)
from src.infrastructure.library.repositories import BookRepository
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.reading.repositories.highlight_repository import HighlightRepository
from src.infrastructure.reading.repositories.reading_session_repository import (
    ReadingSessionRepository,
)
from src.infrastructure.web_reader.repositories.publication_repository import PublicationRepository
from src.infrastructure.web_reader.services.xpoint_cfi_position_anchor_service import (
    XPointCfiPositionAnchorService,
)
from tests.conftest import create_test_book, create_test_highlight, create_test_reading_session
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
)

MINIMAL_EPUB = fixture_bytes("minimal")
MINIMAL_DIGEST = hashlib.sha256(MINIMAL_EPUB).hexdigest()
EPUB_FILE = "minimal-book.epub"
NOT_AN_EPUB = b"PK\x03\x04 not really an EPUB"

SESSION_START_TIME = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

# The third of the four verified ranges: the first paragraph of chapter two,
# which is the paragraph a session's end lands in as well.
OTHER_TEXT, OTHER_START, OTHER_END = FOUR_PLACEABLE[2]
OTHER_SELECTOR = SESSION_END_SELECTOR


class FakeFileStore:
    """A file store that is a dict: only ``get_epub`` is ever reached."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self._files = files

    async def get_epub(self, filename: str | None) -> bytes | None:
        return self._files.get(filename) if filename else None


def build_use_case(db_session: AsyncSession, files: dict[str, bytes]) -> BackfillReadiumRowsUseCase:
    return BackfillReadiumRowsUseCase(
        book_repository=BookRepository(db=db_session),
        file_repository=FakeFileStore(files),  # pyright: ignore[reportArgumentType]
        publication_parser=EpubParserService(),
        publication_repository=PublicationRepository(db=db_session),
        backfill_book_locators_use_case=BackfillBookLocatorsUseCase(
            highlight_repository=HighlightRepository(db=db_session),
            session_repository=ReadingSessionRepository(db=db_session),
            position_anchor_service=XPointCfiPositionAnchorService(),
        ),
    )


async def run_backfill(db_session: AsyncSession, files: dict[str, bytes]) -> ReadiumBackfillReport:
    return await build_use_case(db_session, files).backfill_all()


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
    start: str = PLACEABLE_START,
    end: str = PLACEABLE_END,
) -> models.Highlight:
    return await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=user_id,
        text=text,
        datetime_str="2024-01-15 14:30:22",
        start_xpoint=start,
        end_xpoint=end,
    )


async def xpointed_session(
    db_session: AsyncSession, book: models.Book, user_id: int
) -> models.ReadingSession:
    session = await create_test_reading_session(
        db_session=db_session, book=book, user_id=user_id, start_time=SESSION_START_TIME
    )
    session.start_xpoint = SESSION_START
    session.end_xpoint = SESSION_END
    await db_session.commit()
    await db_session.refresh(session)
    return session


# The repositories write through the session the test holds, so a read has to
# say it wants the row as stored rather than as already loaded.
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


async def second_user(db_session: AsyncSession) -> models.User:
    user = models.User(email="second-reader@test.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def book(db_session: AsyncSession, test_user: models.User) -> models.Book:
    return await book_with_epub(db_session, test_user.id, "Placeable Book")


async def test_a_book_with_an_epub_gets_its_publication_index_and_its_locators(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    session = await xpointed_session(db_session, book, test_user.id)

    report = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    publication = await stored_publication(db_session, book.id)
    assert publication is not None
    assert publication.file_name == EPUB_FILE
    assert publication.content_hash == MINIMAL_DIGEST
    assert [item["href"] for item in publication.publication["reading_order"]] == [
        "OEBPS/chapter1.xhtml",
        "OEBPS/chapter2.xhtml",
    ]

    row = await stored_highlight(db_session, highlight.id)
    assert row.locator is not None
    assert row.locator["href"] == "OEBPS/chapter1.xhtml"
    assert row.locator["locations"]["cssSelector"] == PLACEABLE_SELECTOR
    assert row.locator["text"]["highlight"] == PLACEABLE_TEXT
    assert row.locator_source_hash == MINIMAL_DIGEST

    session_row = await stored_session(db_session, session.id)
    assert session_row.start_locator is not None
    assert session_row.start_locator["locations"]["cssSelector"] == SESSION_START_SELECTOR
    assert session_row.end_locator is not None
    assert session_row.end_locator["locations"]["cssSelector"] == SESSION_END_SELECTOR
    assert session_row.locator_source_hash == MINIMAL_DIGEST

    assert report == ReadiumBackfillReport(
        books_seen=1, books_done=1, epubs_missing=0, books_failed=0
    )


async def test_the_books_of_every_user_are_placed_against_their_owners_rows(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    """Nothing scopes the run to one user; each book's rows are still its owner's."""
    mine = await xpointed_highlight(db_session, book, test_user.id)
    other_user = await second_user(db_session)
    their_book = await book_with_epub(db_session, other_user.id, "Also Placeable")
    theirs = await xpointed_highlight(
        db_session, their_book, other_user.id, OTHER_TEXT, OTHER_START, OTHER_END
    )

    report = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    my_row = await stored_highlight(db_session, mine.id)
    assert my_row.locator is not None
    assert my_row.locator["locations"]["cssSelector"] == PLACEABLE_SELECTOR
    their_row = await stored_highlight(db_session, theirs.id)
    assert their_row.locator is not None
    assert their_row.locator["locations"]["cssSelector"] == OTHER_SELECTOR
    assert their_row.locator["text"]["highlight"] == OTHER_TEXT
    assert await stored_publication(db_session, their_book.id) is not None
    assert report == ReadiumBackfillReport(
        books_seen=2, books_done=2, epubs_missing=0, books_failed=0
    )


async def test_a_book_whose_epub_is_missing_is_skipped_and_the_run_carries_on(
    db_session: AsyncSession, test_user: models.User
) -> None:
    fileless = await book_with_epub(db_session, test_user.id, "Gone", "vanished.epub")
    lost = await xpointed_highlight(db_session, fileless, test_user.id)
    later = await book_with_epub(db_session, test_user.id, "Present")
    placed = await xpointed_highlight(db_session, later, test_user.id, OTHER_TEXT)

    report = await run_backfill(db_session, {EPUB_FILE: MINIMAL_EPUB})

    assert await stored_publication(db_session, fileless.id) is None
    lost_row = await stored_highlight(db_session, lost.id)
    assert lost_row.locator is None
    assert lost_row.locator_source_hash is None
    assert await stored_publication(db_session, later.id) is not None
    assert (await stored_highlight(db_session, placed.id)).locator is not None
    assert report == ReadiumBackfillReport(
        books_seen=2, books_done=1, epubs_missing=1, books_failed=0
    )


async def test_a_book_whose_file_is_not_an_epub_is_counted_failed_and_the_run_carries_on(
    db_session: AsyncSession, test_user: models.User
) -> None:
    broken = await book_with_epub(db_session, test_user.id, "Unreadable", "broken.epub")
    unplaced = await xpointed_highlight(db_session, broken, test_user.id)
    later = await book_with_epub(db_session, test_user.id, "Present")
    placed = await xpointed_highlight(db_session, later, test_user.id, OTHER_TEXT)

    report = await run_backfill(db_session, {"broken.epub": NOT_AN_EPUB, EPUB_FILE: MINIMAL_EPUB})

    assert await stored_publication(db_session, broken.id) is None
    assert (await stored_highlight(db_session, unplaced.id)).locator is None
    assert await stored_publication(db_session, later.id) is not None
    assert (await stored_highlight(db_session, placed.id)).locator is not None
    assert report == ReadiumBackfillReport(
        books_seen=2, books_done=1, epubs_missing=0, books_failed=1
    )


async def test_rows_derived_from_another_file_are_overwritten(
    db_session: AsyncSession, test_user: models.User, book: models.Book
) -> None:
    highlight = await xpointed_highlight(db_session, book, test_user.id)
    highlight.locator_source_hash = "stale"
    session = await xpointed_session(db_session, book, test_user.id)
    session.locator_source_hash = "stale"
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
    assert (await stored_session(db_session, session.id)).locator_source_hash == MINIMAL_DIGEST
