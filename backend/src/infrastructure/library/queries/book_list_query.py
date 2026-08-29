"""Query adapter for the two book-list views.

Rows map straight to view DTOs. The old path came out of the repository as
``list[tuple[Book, int, int]]``: every row was hydrated into a ``Book``
aggregate -- value objects, invariant checks and all -- so that a list could
render a dozen columns. Queries select, join, filter, order and group; they
never decide anything.
"""

from datetime import datetime

from sqlalchemy import ColumnElement, Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from src.application.library.queries.book_list import BookListPageView, BookWithCountsView
from src.domain.common.value_objects.ids import UserId
from src.domain.common.value_objects.position import Position
from src.domain.library.entities.book import ReadingStage
from src.infrastructure.common.sql import LIKE_ESCAPE_CHAR, escape_like_pattern
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM


def _book_rows() -> Select[tuple[BookORM, int, int]]:
    """Select a book row with its highlight and flashcard counts.

    Built per call rather than held as a module constant: ``noload`` resolves
    the relationship eagerly, which would configure the ORM mappers while this
    module is still being imported, before every model is registered.

    Both lists render most of the book row, so the whole entity is selected
    rather than a column list. ``Book.tag_groups`` is ``lazy="selectin"``, which
    would otherwise cost an extra round trip per page for data neither list
    shows.
    """
    highlight_count = (
        select(func.count(HighlightORM.id))
        .where(
            HighlightORM.book_id == BookORM.id,
            HighlightORM.deleted_at.is_(None),
        )
        .correlate(BookORM)
        .scalar_subquery()
        .label("highlight_count")
    )
    flashcard_count = (
        select(func.count(FlashcardORM.id))
        .where(FlashcardORM.book_id == BookORM.id)
        .correlate(BookORM)
        .scalar_subquery()
        .label("flashcard_count")
    )
    return select(BookORM, highlight_count, flashcard_count).options(noload(BookORM.tag_groups))


class BookListQuery:
    """Serves the book-list read models from purpose-built selects."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_books(
        self,
        user_id: UserId,
        offset: int,
        limit: int,
        include_only_with_flashcards: bool,
        search_text: str | None,
    ) -> BookListPageView:
        """Return a page of the user's books ordered by title, plus the total."""
        filters = _filters(user_id, include_only_with_flashcards, search_text)

        total_stmt = select(func.count(BookORM.id)).where(*filters)
        total = (await self.db.execute(total_stmt)).scalar() or 0

        stmt = _book_rows().where(*filters).order_by(BookORM.title).offset(offset).limit(limit)
        return BookListPageView(books=await self._fetch(stmt), total=total)

    async def list_recent(self, user_id: UserId, limit: int) -> tuple[BookWithCountsView, ...]:
        """Return the books last opened or synced, most recent of the two first."""
        stmt = (
            _book_rows()
            .where(
                BookORM.user_id == user_id.value,
                or_(BookORM.last_viewed.isnot(None), BookORM.last_synced.isnot(None)),
            )
            .order_by(_recency().desc())
            .limit(limit)
        )
        return await self._fetch(stmt)

    async def _fetch(
        self, stmt: Select[tuple[BookORM, int, int]]
    ) -> tuple[BookWithCountsView, ...]:
        """Run a book-row select and map every row to its view DTO."""
        rows = (await self.db.execute(stmt)).all()
        return tuple(
            _book_view(book, highlight_count, flashcard_count)
            for book, highlight_count, flashcard_count in rows
        )


def _recency() -> ColumnElement[datetime | None]:
    """The later of a book's two activity stamps, which the recent list orders by.

    Spelled as a ``CASE`` rather than ``GREATEST``: that function is Postgres-only,
    and the tests run on SQLite, where two-argument ``MAX`` means something else.
    """
    return case(
        (BookORM.last_viewed.is_(None), BookORM.last_synced),
        (BookORM.last_synced.is_(None), BookORM.last_viewed),
        (BookORM.last_viewed > BookORM.last_synced, BookORM.last_viewed),
        else_=BookORM.last_synced,
    )


def _filters(
    user_id: UserId, include_only_with_flashcards: bool, search_text: str | None
) -> list[ColumnElement[bool]]:
    """Build the predicates shared by the page query and its total count."""
    filters: list[ColumnElement[bool]] = [BookORM.user_id == user_id.value]

    if search_text:
        pattern = f"%{escape_like_pattern(search_text)}%"
        filters.append(
            BookORM.title.ilike(pattern, escape=LIKE_ESCAPE_CHAR)
            | BookORM.author.ilike(pattern, escape=LIKE_ESCAPE_CHAR)
        )

    if include_only_with_flashcards:
        filters.append(select(1).where(FlashcardORM.book_id == BookORM.id).exists())

    return filters


def _book_view(row: BookORM, highlight_count: int, flashcard_count: int) -> BookWithCountsView:
    """Map a book row and its counts to the view DTO."""
    return BookWithCountsView(
        id=row.id,
        client_book_id=row.client_book_id,
        title=row.title,
        author=row.author,
        isbn=row.isbn,
        cover_file=row.cover_file,
        cover_blurhash=row.cover_blurhash,
        description=row.description,
        language=row.language,
        page_count=row.page_count,
        highlight_count=highlight_count,
        flashcard_count=flashcard_count,
        reading_stage=ReadingStage(row.reading_stage) if row.reading_stage else None,
        end_position=Position.from_json(row.end_position) if row.end_position else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_viewed=row.last_viewed,
        last_synced=row.last_synced,
    )
