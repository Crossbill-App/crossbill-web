"""Query adapter reading the canonical positions highlight locators derive from.

Two selects with the same column list and the same filters, differing only in
what identifies the rows: a book, or one highlight. Both answer the same DTO, so
the derivation above them has one shape to handle.

A malformed xpointer is read as *no* xpointer rather than raising. The columns
are free text written by a device, and one unparseable row must not take a
book's whole highlight list down with it -- the highlight is reported as
unplaceable, which is what it is.
"""

import logging
from collections.abc import Collection, Sequence

from sqlalchemy import Row, Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.web_reader.queries.highlight_locators import (
    BookHighlightAnchors,
    HighlightAnchor,
)
from src.domain.common.exceptions import XPointParseError
from src.domain.common.value_objects.ids import BookId, HighlightId, UserId
from src.domain.common.value_objects.xpoint import XPointRange
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM

logger = logging.getLogger(__name__)

type _AnchorRow = Row[tuple[int, str, str | None, str | None, str | None]]


def _anchor_rows() -> Select[tuple[int, str, str | None, str | None, str | None]]:
    """The select every anchor lookup narrows.

    Built per call rather than held at module scope: an adapter is imported from
    the container early enough that a shared statement configures the ORM
    mappers before every model is registered (see ``docs/agents/read-models.md``).
    """
    return select(
        HighlightORM.id,
        HighlightORM.text,
        HighlightORM.start_xpoint,
        HighlightORM.end_xpoint,
        BookORM.ebook_file,
    ).join(BookORM, BookORM.id == HighlightORM.book_id)


class HighlightAnchorQuery:
    """Serves highlight xpointers and text, scoped to their owner."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with the session the rows are read from."""
        self.db = db

    async def anchors_for_book(
        self,
        book_id: BookId,
        user_id: UserId,
        highlight_ids: Collection[int] | None = None,
    ) -> BookHighlightAnchors | None:
        """Return the book's live highlights, or ``None`` if the user has no such book."""
        if not await self._owns_book(book_id, user_id):
            return None
        stmt = (
            _anchor_rows()
            .where(
                HighlightORM.book_id == book_id.value,
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
            .order_by(HighlightORM.id)
        )
        if highlight_ids is not None:
            stmt = stmt.where(HighlightORM.id.in_(highlight_ids))
        rows = (await self.db.execute(stmt)).all()
        ebook_file = await self._ebook_file(book_id, user_id)
        return _anchors(ebook_file, rows)

    async def anchor_for_highlight(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> BookHighlightAnchors | None:
        """Return one live highlight, or ``None`` if the user has no such highlight."""
        stmt = _anchor_rows().where(
            HighlightORM.id == highlight_id.value,
            HighlightORM.user_id == user_id.value,
            HighlightORM.deleted_at.is_(None),
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return _anchors(row.ebook_file, [row])

    async def _owns_book(self, book_id: BookId, user_id: UserId) -> bool:
        """Report whether the book exists and belongs to the user."""
        stmt = select(BookORM.id).where(
            BookORM.id == book_id.value,
            BookORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).first() is not None

    async def _ebook_file(self, book_id: BookId, user_id: UserId) -> str | None:
        """The book's stored EPUB filename.

        Read separately rather than off the highlight join, so that a book with
        no highlights still reports whether it has an EPUB.
        """
        stmt = select(BookORM.ebook_file).where(
            BookORM.id == book_id.value,
            BookORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


def _anchors(ebook_file: str | None, rows: Sequence[_AnchorRow]) -> BookHighlightAnchors:
    """Map anchor rows to the view DTO."""
    return BookHighlightAnchors(
        ebook_file=ebook_file,
        highlights=tuple(
            HighlightAnchor(
                highlight_id=row.id,
                xpoints=_xpoints(row.id, row.start_xpoint, row.end_xpoint),
                text=row.text,
            )
            for row in rows
        ),
    )


def _xpoints(highlight_id: int, start: str | None, end: str | None) -> XPointRange | None:
    """Parse a stored range, reading anything unusable as no range at all."""
    if not start or not end:
        return None
    try:
        return XPointRange.parse(start, end)
    except (ValueError, XPointParseError) as exc:
        logger.info("unparseable_highlight_xpoints", extra={"id": highlight_id, "reason": str(exc)})
        return None
