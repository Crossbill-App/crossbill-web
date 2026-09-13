"""Query adapter reading the locators stored on a book's highlights."""

from typing import Any

from sqlalchemy import Row, Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.web_reader.anchors import Locator
from src.application.web_reader.queries.highlight_locators import (
    BookHighlightLocators,
    HighlightLocatorInBook,
    StoredHighlightLocator,
)
from src.domain.common.value_objects.ids import BookId, HighlightId, UserId
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.web_reader.orm.book_publication_model import (
    BookPublication as BookPublicationORM,
)


class HighlightLocatorQuery:
    """Reads locator columns and nothing else -- no EPUB, no parser, no derivation."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def locators_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> BookHighlightLocators | None:
        """Return the book's stored locators, or ``None`` if the user has no such book."""
        result = await self.db.execute(_locator_rows(book_id, user_id))
        rows = result.all()
        if not rows:
            return None
        return BookHighlightLocators(
            publication_hash=rows[0].content_hash,
            # A book with no live highlights still answers one row, whose
            # highlight columns are the outer join's nulls.
            highlights=tuple(_stored_locator(row) for row in rows if row.id is not None),
        )

    async def locator_for_highlight(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> HighlightLocatorInBook | None:
        """Return one highlight's stored locator, or ``None`` if the user has no live one."""
        result = await self.db.execute(_highlight_locator_row(highlight_id, user_id))
        row = result.one_or_none()
        if row is None:
            return None
        return HighlightLocatorInBook(
            publication_hash=row.content_hash, highlight=_stored_locator(row)
        )


def _stored_locator(row: Row[Any]) -> StoredHighlightLocator:
    return StoredHighlightLocator(
        highlight_id=row.id,
        locator=Locator.from_dict(row.locator) if row.locator else None,
        source_hash=row.locator_source_hash,
    )


# `Select[Any]`, not the four columns: a Row's attributes are `Any` whichever is
# declared, and naming them would claim the two the outer joins can null are not.
def _locator_rows(book_id: BookId, user_id: UserId) -> Select[Any]:
    # The book is the driving table so that a book with no highlights still
    # yields a row: an empty result is the only signal for "no such book", and a
    # book with nothing in it must not be answered with a 404.
    return (
        select(
            BookPublicationORM.content_hash,
            HighlightORM.id,
            HighlightORM.locator,
            HighlightORM.locator_source_hash,
        )
        .select_from(BookORM)
        .outerjoin(BookPublicationORM, BookPublicationORM.book_id == BookORM.id)
        .outerjoin(
            HighlightORM,
            and_(
                HighlightORM.book_id == BookORM.id,
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            ),
        )
        .where(BookORM.id == book_id.value, BookORM.user_id == user_id.value)
        .order_by(HighlightORM.id)
    )


def _highlight_locator_row(highlight_id: HighlightId, user_id: UserId) -> Select[Any]:
    # The highlight is the driving table and carries its own user, so the book
    # row's owner is not checked: R4.2 leaves a stranger's highlights on another
    # user's book row, and each of those is its owner's to read.
    return (
        select(
            BookPublicationORM.content_hash,
            HighlightORM.id,
            HighlightORM.locator,
            HighlightORM.locator_source_hash,
        )
        .select_from(HighlightORM)
        .outerjoin(BookPublicationORM, BookPublicationORM.book_id == HighlightORM.book_id)
        .where(
            HighlightORM.id == highlight_id.value,
            HighlightORM.user_id == user_id.value,
            HighlightORM.deleted_at.is_(None),
        )
    )
