"""Tests for the book-list read model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import UserId
from src.infrastructure.library.queries.book_list_query import BookListQuery
from src.models import Book, Flashcard, User
from tests.conftest import create_test_book, create_test_highlight

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2


@pytest.fixture
def query(db_session: AsyncSession) -> BookListQuery:
    """The query service wired the way the container wires it."""
    return BookListQuery(db=db_session)


async def add_flashcard(db_session: AsyncSession, book: Book, user_id: int) -> Flashcard:
    """Attach a flashcard to a book."""
    card = Flashcard(user_id=user_id, book_id=book.id, question="Q", answer="A")
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


async def stamp(
    db_session: AsyncSession,
    book: Book,
    viewed: datetime | None = None,
    synced: datetime | None = None,
) -> None:
    """Set a book's activity stamps, which is what puts it on the recent list."""
    book.last_viewed = viewed
    book.last_synced = synced
    await db_session.commit()


async def add_one_of_each_countable(db_session: AsyncSession, book: Book) -> None:
    """A live highlight, a soft-deleted one that must not be counted, and a flashcard."""
    await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text="Kept",
        datetime_str="2024-01-15 14:30:22",
    )
    await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text="Gone",
        datetime_str="2024-01-15 14:31:22",
        deleted_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    await add_flashcard(db_session, book, DEFAULT_USER_ID)


async def test_books_are_ordered_by_title_with_zero_counts(
    query: BookListQuery, db_session: AsyncSession
) -> None:
    await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Zebra")
    await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Aardvark")

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=0,
        limit=100,
        include_only_with_flashcards=False,
        search_text=None,
    )

    assert [(b.title, b.highlight_count, b.flashcard_count) for b in page.books] == [
        ("Aardvark", 0, 0),
        ("Zebra", 0, 0),
    ]
    assert page.total == 2


async def test_counts_exclude_soft_deleted_highlights(
    query: BookListQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await add_one_of_each_countable(db_session, test_book)

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=0,
        limit=100,
        include_only_with_flashcards=False,
        search_text=None,
    )

    assert [(b.highlight_count, b.flashcard_count) for b in page.books] == [(1, 1)]


async def test_another_users_books_are_invisible(
    query: BookListQuery, db_session: AsyncSession, test_book: Book, other_user: User
) -> None:
    await create_test_book(db_session=db_session, user_id=OTHER_USER_ID, title="Not Mine")

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=0,
        limit=100,
        include_only_with_flashcards=False,
        search_text=None,
    )

    assert [b.title for b in page.books] == [test_book.title]
    assert page.total == 1


async def test_total_counts_every_match_while_the_page_is_limited(
    query: BookListQuery, db_session: AsyncSession
) -> None:
    for title in ("A", "B", "C"):
        await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title=title)

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=1,
        limit=1,
        include_only_with_flashcards=False,
        search_text=None,
    )

    assert [b.title for b in page.books] == ["B"]
    assert page.total == 3


async def test_search_matches_title_or_author_case_insensitively(
    query: BookListQuery, db_session: AsyncSession
) -> None:
    await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Dune", author="Herbert"
    )
    await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Emma", author="dunedin Press"
    )
    await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Ulysses")

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=0,
        limit=100,
        include_only_with_flashcards=False,
        search_text="DUNE",
    )

    assert [b.title for b in page.books] == ["Dune", "Emma"]
    assert page.total == 2


async def test_search_treats_wildcards_as_literal_text(
    query: BookListQuery, db_session: AsyncSession
) -> None:
    """A ``%`` in the search text must not match everything."""
    await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="100% Cotton")
    await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Plain")

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=0,
        limit=100,
        include_only_with_flashcards=False,
        search_text="0%",
    )

    assert [b.title for b in page.books] == ["100% Cotton"]
    assert page.total == 1


async def test_flashcard_filter_keeps_only_books_with_cards(
    query: BookListQuery, db_session: AsyncSession
) -> None:
    with_cards = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Has cards"
    )
    await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="No cards")
    await add_flashcard(db_session, with_cards, DEFAULT_USER_ID)

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=0,
        limit=100,
        include_only_with_flashcards=True,
        search_text=None,
    )

    assert [b.title for b in page.books] == ["Has cards"]
    assert page.total == 1


async def test_recent_skips_books_never_opened_or_synced(
    query: BookListQuery, db_session: AsyncSession
) -> None:
    older = await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Older")
    newer = await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Newer")
    await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Untouched")
    await stamp(db_session, older, viewed=datetime(2024, 1, 1, tzinfo=UTC))
    await stamp(db_session, newer, viewed=datetime(2024, 6, 1, tzinfo=UTC))

    books = await query.list_recent(user_id=UserId(DEFAULT_USER_ID), limit=10)

    assert [b.title for b in books] == ["Newer", "Older"]


async def test_recent_ranks_viewed_and_synced_books_against_each_other(
    query: BookListQuery, db_session: AsyncSession
) -> None:
    """One list, two kinds of stamp: whichever moment is later ranks higher."""
    viewed = await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Viewed")
    synced = await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Synced")
    await stamp(db_session, viewed, viewed=datetime(2024, 3, 1, tzinfo=UTC))
    await stamp(db_session, synced, synced=datetime(2024, 6, 1, tzinfo=UTC))

    books = await query.list_recent(user_id=UserId(DEFAULT_USER_ID), limit=10)

    assert [b.title for b in books] == ["Synced", "Viewed"]


@pytest.mark.parametrize(
    ("viewed", "synced"),
    [
        (datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 9, 1, tzinfo=UTC)),
        (datetime(2024, 9, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)),
    ],
    ids=["synced last", "viewed last"],
)
async def test_recent_ranks_a_book_by_the_later_of_its_two_stamps(
    query: BookListQuery,
    db_session: AsyncSession,
    viewed: datetime,
    synced: datetime,
) -> None:
    """A book carrying both stamps is placed by the newer one, and listed once.

    Run from both sides so an inverted comparison cannot pass.
    """
    both = await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Both")
    other = await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title="Other")
    await stamp(db_session, both, viewed=viewed, synced=synced)
    await stamp(db_session, other, viewed=datetime(2024, 6, 1, tzinfo=UTC))

    books = await query.list_recent(user_id=UserId(DEFAULT_USER_ID), limit=10)

    assert [b.title for b in books] == ["Both", "Other"]


async def test_recent_excludes_another_users_books(
    query: BookListQuery, db_session: AsyncSession, test_book: Book, other_user: User
) -> None:
    theirs = await create_test_book(db_session=db_session, user_id=OTHER_USER_ID, title="Not Mine")
    await stamp(db_session, test_book, viewed=datetime(2024, 1, 1, tzinfo=UTC))
    await stamp(db_session, theirs, viewed=datetime(2024, 6, 1, tzinfo=UTC))

    books = await query.list_recent(user_id=UserId(DEFAULT_USER_ID), limit=10)

    assert [b.title for b in books] == [test_book.title]


async def test_recent_honours_the_limit(query: BookListQuery, db_session: AsyncSession) -> None:
    for index, title in enumerate(("A", "B", "C")):
        book = await create_test_book(db_session=db_session, user_id=DEFAULT_USER_ID, title=title)
        await stamp(db_session, book, viewed=datetime(2024, 1, index + 1, tzinfo=UTC))

    books = await query.list_recent(user_id=UserId(DEFAULT_USER_ID), limit=2)

    assert [b.title for b in books] == ["C", "B"]


async def test_recent_carries_the_same_counts_as_the_library_list(
    query: BookListQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await add_one_of_each_countable(db_session, test_book)
    await stamp(db_session, test_book, viewed=datetime(2024, 6, 1, tzinfo=UTC))

    books = await query.list_recent(user_id=UserId(DEFAULT_USER_ID), limit=10)

    assert [(b.highlight_count, b.flashcard_count) for b in books] == [(1, 1)]


async def test_end_position_is_read_back_as_a_position(
    query: BookListQuery, db_session: AsyncSession, test_book: Book
) -> None:
    test_book.end_position = [42, 7]
    await db_session.commit()

    page = await query.list_books(
        user_id=UserId(DEFAULT_USER_ID),
        offset=0,
        limit=100,
        include_only_with_flashcards=False,
        search_text=None,
    )

    end_position = page.books[0].end_position
    assert end_position is not None
    assert (end_position.index, end_position.char_index) == (42, 7)
