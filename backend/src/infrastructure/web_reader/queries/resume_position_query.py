"""Query adapter reading the two stored places a book can be resumed from."""

from typing import Any

from sqlalchemy import Row, Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.web_reader.anchors import Locator
from src.application.web_reader.queries.resume_position import (
    BrowserPosition,
    DevicePosition,
    ResumeCandidates,
)
from src.domain.common.devices import WEB_READER_DEVICE_ID
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.reading.orm.reading_session_model import (
    ReadingSession as ReadingSessionORM,
)
from src.infrastructure.web_reader.orm.book_publication_model import (
    BookPublication as BookPublicationORM,
)
from src.infrastructure.web_reader.orm.web_reading_position_model import (
    WebReadingPosition as WebReadingPositionORM,
)


class ResumePositionQuery:
    """Reads stored position columns and nothing else -- no EPUB, no parser, no derivation."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resume_candidates(self, book_id: BookId, user_id: UserId) -> ResumeCandidates | None:
        """Return the book's stored places, or ``None`` if the user has no such book."""
        result = await self.db.execute(_browser_row(book_id, user_id))
        row = result.one_or_none()
        if row is None:
            return None
        return ResumeCandidates(
            publication_hash=row.content_hash,
            browser=_browser_position(row),
            device=await self._device_position(book_id, user_id),
        )

    async def _device_position(self, book_id: BookId, user_id: UserId) -> DevicePosition | None:
        result = await self.db.execute(_device_row(book_id, user_id))
        row = result.one_or_none()
        if row is None:
            return None
        return DevicePosition(
            locator=Locator.from_dict(row.end_locator) if row.end_locator else None,
            source_hash=row.locator_source_hash,
            ended_at=row.end_time,
        )


def _browser_position(row: Row[Any]) -> BrowserPosition | None:
    # `recorded_at` is not nullable on the row, so a null one is the outer join's.
    if row.recorded_at is None:
        return None
    return BrowserPosition(
        locator=row.locator,
        source_hash=row.locator_source_hash,
        recorded_at=row.recorded_at,
    )


# `Select[Any]`, not the named columns: a Row's attributes are `Any` whichever is
# declared, and naming them would claim the ones the outer joins can null are not.
def _browser_row(book_id: BookId, user_id: UserId) -> Select[Any]:
    # The book is the driving table so that a book nobody has opened still yields
    # a row: an empty result is the only signal for "no such book", and a book
    # with nothing stored against it must not be answered with a 404.
    return (
        select(
            BookPublicationORM.content_hash,
            WebReadingPositionORM.locator,
            WebReadingPositionORM.locator_source_hash,
            WebReadingPositionORM.recorded_at,
        )
        .select_from(BookORM)
        .outerjoin(BookPublicationORM, BookPublicationORM.book_id == BookORM.id)
        .outerjoin(
            WebReadingPositionORM,
            and_(
                WebReadingPositionORM.book_id == BookORM.id,
                WebReadingPositionORM.user_id == user_id.value,
            ),
        )
        .where(BookORM.id == book_id.value, BookORM.user_id == user_id.value)
    )


def _device_row(book_id: BookId, user_id: UserId) -> Select[Any]:
    # A session with no end xpointer never said where the reader got to, so it is
    # no candidate however recent; one that said where but carries no usable
    # locator is a candidate, and answers that the place cannot be placed.
    #
    # Sessions the web reader itself wrote are left out: one describes the same
    # moment as the position row beside it, but by the server's clock rather than
    # the reader's, so it would win ties it says nothing new about.
    return (
        select(
            ReadingSessionORM.end_locator,
            ReadingSessionORM.locator_source_hash,
            ReadingSessionORM.end_time,
        )
        .where(
            ReadingSessionORM.book_id == book_id.value,
            ReadingSessionORM.user_id == user_id.value,
            ReadingSessionORM.end_xpoint.is_not(None),
            or_(
                ReadingSessionORM.device_id.is_(None),
                ReadingSessionORM.device_id != WEB_READER_DEVICE_ID,
            ),
        )
        .order_by(ReadingSessionORM.end_time.desc(), ReadingSessionORM.id.desc())
        .limit(1)
    )
