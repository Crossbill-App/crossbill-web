"""Shared scaffolding for the infrastructure-level read-model tests.

Every query test wires its query service against the real in-memory SQLite
session, so they all need the same three things: the label resolution service
the container injects, a second user to prove ownership scoping, and chapters
to hang highlights off.
"""

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.reading.services.highlight_style_resolver import HighlightStyleResolver
from src.infrastructure.reading.repositories.highlight_style_repository import (
    HighlightStyleRepository,
)
from src.models import Book, Chapter, HighlightStyle, User
from tests.conftest import create_test_chapter, create_test_highlight_style

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2
LABEL_TEXT = "Key idea"
LABEL_UI_COLOR = "#ffcc00"

AddChapter = Callable[..., Awaitable[Chapter]]


@pytest.fixture
def label_resolution_service(db_session: AsyncSession) -> LabelResolutionService:
    """The label resolution service wired the way the container wires it."""
    return LabelResolutionService(
        highlight_style_repository=HighlightStyleRepository(db_session),
        highlight_style_resolver=HighlightStyleResolver(),
    )


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """A second user, to check ownership scoping."""
    user = User(id=OTHER_USER_ID, email="other@test.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def add_chapter(db_session: AsyncSession) -> AddChapter:
    """Attach a chapter to a book."""

    async def _add_chapter(
        book: Book,
        name: str,
        chapter_number: int | None = None,
        parent_id: int | None = None,
    ) -> Chapter:
        return await create_test_chapter(db_session, book, name, chapter_number, parent_id)

    return _add_chapter


@pytest.fixture
async def labelled_style(db_session: AsyncSession, test_book: Book) -> HighlightStyle:
    """A style carrying the label the resolution service is expected to surface."""
    return await create_test_highlight_style(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        book_id=test_book.id,
        device_color="yellow",
        device_style="lighten",
        label=LABEL_TEXT,
        ui_color=LABEL_UI_COLOR,
    )
