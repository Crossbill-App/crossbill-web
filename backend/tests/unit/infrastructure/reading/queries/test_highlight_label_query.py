"""Tests for the highlight-label read model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.highlight_style_resolver import HighlightStyleResolver
from src.infrastructure.reading.queries.highlight_label_query import HighlightLabelQuery
from src.infrastructure.reading.repositories.highlight_style_repository import (
    HighlightStyleRepository,
)
from src.models import Book, HighlightStyle, User
from tests.conftest import create_test_highlight, create_test_highlight_style

DEFAULT_USER_ID = 1


@pytest.fixture
def query(db_session: AsyncSession) -> HighlightLabelQuery:
    """The query service wired the way the container wires it."""
    return HighlightLabelQuery(
        db=db_session,
        label_resolution_service=LabelResolutionService(
            highlight_style_repository=HighlightStyleRepository(db_session),
            highlight_style_resolver=HighlightStyleResolver(),
        ),
    )


async def add_global_style(
    db_session: AsyncSession,
    user_id: int,
    device_color: str | None = "yellow",
    device_style: str | None = "lighten",
    label: str | None = None,
) -> HighlightStyle:
    """Create a global (bookless) highlight style."""
    style = HighlightStyle(
        user_id=user_id,
        book_id=None,
        device_color=device_color,
        device_style=device_style,
        label=label,
    )
    db_session.add(style)
    await db_session.commit()
    await db_session.refresh(style)
    return style


async def add_other_user(db_session: AsyncSession) -> User:
    """Create a second user to check ownership scoping."""
    other = User(id=2, email="other@test.com")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    return other


async def test_missing_book_is_distinguished_from_a_book_without_labels(
    query: HighlightLabelQuery, test_book: Book
) -> None:
    assert await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID)) == ()
    assert await query.list_for_book(BookId(test_book.id + 999), UserId(DEFAULT_USER_ID)) is None


async def test_another_users_book_is_invisible(
    query: HighlightLabelQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await create_test_highlight_style(
        db_session=db_session, user_id=DEFAULT_USER_ID, book_id=test_book.id, label="Mine"
    )
    other = await add_other_user(db_session)

    assert await query.list_for_book(BookId(test_book.id), UserId(other.id)) is None


async def test_counts_live_highlights_per_style(
    query: HighlightLabelQuery, db_session: AsyncSession, test_book: Book
) -> None:
    style = await create_test_highlight_style(
        db_session=db_session, user_id=DEFAULT_USER_ID, book_id=test_book.id, label="Important"
    )
    unused = await create_test_highlight_style(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        book_id=test_book.id,
        device_color="blue",
        label="Unused",
    )
    for index in range(2):
        await create_test_highlight(
            db_session=db_session,
            book=test_book,
            user_id=DEFAULT_USER_ID,
            text=f"Counted {index}",
            datetime_str=f"2024-01-1{index} 10:00:00",
            highlight_style_id=style.id,
        )
    await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        text="Soft deleted",
        datetime_str="2024-01-20 10:00:00",
        highlight_style_id=style.id,
        deleted_at=datetime.now(UTC),
    )

    labels = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert labels is not None
    counts = {label.id: label.highlight_count for label in labels}
    assert counts == {style.id: 2, unused.id: 0}


async def test_book_labels_carry_the_resolved_label_and_its_source(
    query: HighlightLabelQuery, db_session: AsyncSession, test_book: Book
) -> None:
    # The book-scoped combination has no label of its own, so resolution has to
    # fall back to the global combination -- the rule the service owns.
    style = await create_test_highlight_style(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        book_id=test_book.id,
        device_color="yellow",
        device_style="lighten",
    )
    await add_global_style(db_session, DEFAULT_USER_ID, label="Key idea")

    labels = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert labels is not None
    assert len(labels) == 1
    assert labels[0].id == style.id
    assert labels[0].label == "Key idea"
    assert labels[0].label_source == "global"
    assert labels[0].device_color == "yellow"
    assert labels[0].device_style == "lighten"


async def test_global_list_excludes_book_scoped_styles_and_reports_no_counts(
    query: HighlightLabelQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await create_test_highlight_style(
        db_session=db_session, user_id=DEFAULT_USER_ID, book_id=test_book.id, label="Book scoped"
    )
    global_style = await add_global_style(db_session, DEFAULT_USER_ID, label="Everywhere")

    labels = await query.list_global(UserId(DEFAULT_USER_ID))

    assert [label.id for label in labels] == [global_style.id]
    assert labels[0].label == "Everywhere"
    assert labels[0].label_source == "global"
    assert labels[0].highlight_count == 0


async def test_global_list_is_scoped_to_the_user(
    query: HighlightLabelQuery, db_session: AsyncSession
) -> None:
    await add_global_style(db_session, DEFAULT_USER_ID, label="Mine")
    other = await add_other_user(db_session)
    await add_global_style(db_session, other.id, device_color="red", label="Theirs")

    labels = await query.list_global(UserId(DEFAULT_USER_ID))

    assert [label.label for label in labels] == ["Mine"]
