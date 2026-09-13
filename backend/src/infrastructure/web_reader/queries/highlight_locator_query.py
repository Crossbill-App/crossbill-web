"""Query adapter reading the locators stored on a book's highlights."""

from typing import Any

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.web_reader.anchors import Locator
from src.application.web_reader.queries.highlight_locators import (
    BookHighlightLocators,
    StoredHighlightLocator,
)
from src.domain.common.value_objects.ids import BookId, UserId
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
            highlights=tuple(
                StoredHighlightLocator(
                    highlight_id=row.id,
                    locator=Locator.from_dict(row.locator) if row.locator else None,
                    source_hash=row.locator_source_hash,
                )
                # A book with no live highlights still answers one row, whose
                # highlight columns are the outer join's nulls.
                for row in rows
                if row.id is not None
            ),
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
