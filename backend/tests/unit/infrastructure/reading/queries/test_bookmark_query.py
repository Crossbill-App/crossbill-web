"""Tests for the bookmark-list read model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.reading.queries.bookmark_query import BookmarkQuery
from src.models import Book, Bookmark, Highlight, User
from tests.conftest import create_test_book, create_test_highlight

DEFAULT_USER_ID = 1


@pytest.fixture
def query(db_session: AsyncSession) -> BookmarkQuery:
    """The query service wired the way the container wires it."""
    return BookmarkQuery(db=db_session)


async def add_bookmark(db_session: AsyncSession, book: Book, highlight: Highlight) -> Bookmark:
    """Pin a bookmark to a highlight."""
    bookmark = Bookmark(book_id=book.id, highlight_id=highlight.id)
    db_session.add(bookmark)
    await db_session.commit()
    await db_session.refresh(bookmark)
    return bookmark


async def add_other_user(db_session: AsyncSession) -> User:
    """Create a second user to check ownership scoping."""
    other = User(id=2, email="other@test.com")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    return other


async def test_book_without_bookmarks_returns_empty_tuple(
    query: BookmarkQuery, test_book: Book
) -> None:
    assert await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID)) == ()


async def test_missing_book_is_distinguished_from_an_empty_one(
    query: BookmarkQuery, test_book: Book
) -> None:
    assert await query.list_for_book(BookId(test_book.id + 999), UserId(DEFAULT_USER_ID)) is None


async def test_bookmarks_are_returned_newest_first(
    query: BookmarkQuery,
    db_session: AsyncSession,
    test_book: Book,
    test_highlight: Highlight,
) -> None:
    second = await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        text="Second highlight",
        datetime_str="2024-01-16 09:00:00",
    )
    older = await add_bookmark(db_session, test_book, test_highlight)
    newer = await add_bookmark(db_session, test_book, second)
    # Both rows land on the same server_default timestamp under SQLite, so pin
    # them apart explicitly rather than relying on insertion speed.
    older.created_at = older.created_at.replace(year=2023)
    await db_session.commit()

    bookmarks = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert bookmarks is not None
    assert [b.id for b in bookmarks] == [newer.id, older.id]
    assert bookmarks[0].book_id == test_book.id
    assert bookmarks[0].highlight_id == second.id


async def test_another_users_book_is_invisible(
    query: BookmarkQuery,
    db_session: AsyncSession,
    test_book: Book,
    test_highlight: Highlight,
) -> None:
    await add_bookmark(db_session, test_book, test_highlight)
    other = await add_other_user(db_session)

    assert await query.list_for_book(BookId(test_book.id), UserId(other.id)) is None


async def test_bookmarks_of_another_book_are_not_included(
    query: BookmarkQuery,
    db_session: AsyncSession,
    test_book: Book,
    test_highlight: Highlight,
) -> None:
    other_book = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Other Book"
    )
    other_highlight = await create_test_highlight(
        db_session=db_session,
        book=other_book,
        user_id=DEFAULT_USER_ID,
        text="Elsewhere",
        datetime_str="2024-02-01 10:00:00",
    )
    mine = await add_bookmark(db_session, test_book, test_highlight)
    await add_bookmark(db_session, other_book, other_highlight)

    bookmarks = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert bookmarks is not None
    assert [b.id for b in bookmarks] == [mine.id]
