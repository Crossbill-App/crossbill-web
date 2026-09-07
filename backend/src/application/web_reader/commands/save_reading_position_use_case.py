"""Record where a reader has got to in a book they are reading in the browser."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import structlog

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.reading_session_repository import (
    ReadingSessionRepositoryProtocol,
)
from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorResolutionError,
    Locator,
)
from src.application.web_reader.protocols.book_position_index import BookPositionIndexProtocol
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.application.web_reader.protocols.web_reading_position_repository import (
    WebReadingPositionRepositoryProtocol,
)
from src.config import get_settings
from src.domain.common.time import as_aware
from src.domain.common.value_objects import (
    BookId,
    ReadingSessionId,
    UserId,
    XPoint,
    XPointRange,
)
from src.domain.common.value_objects.position import Position
from src.domain.library.entities.book import Book
from src.domain.library.exceptions import EbookFileNotFoundError
from src.domain.reading.entities.reading_session import ReadingSession
from src.domain.reading.exceptions import BookNotFoundError
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition
from src.domain.web_reader.exceptions import UnresolvablePositionError

logger = structlog.get_logger(__name__)

# The weakest match this will store a position from.
#
# Resolving a browser locator back to an xpointer is a text search that grades
# itself (ADR-0004 §5), and this floor is where "we know which place this is"
# begins. The two grades below it are the two that mean the opposite: FUZZY is
# the quote not being in the book as written -- the shape a replaced, differently
# typeset EPUB takes -- and AMBIGUOUS is the quote being in several places with
# neither context settling which. HIGHLIGHT_ONLY and above all identify exactly
# one place in the document.
#
# Deliberately one grade below what a *highlight* will demand (M4.1). A
# highlight drawn in the wrong paragraph is a visible, lasting falsehood about
# what the reader marked; a reading position that is off costs them a moment
# finding their place. Rejecting a unique quote merely for having no abutting
# context would trade a great many unrecorded positions for that difference.
MINIMUM_POSITION_CONFIDENCE = AnchorConfidence.HIGHLIGHT_ONLY

# What a session created by the web reader records as its device, so that
# browser reading is distinguishable from an e-reader's in the sessions list --
# and so that its content hash cannot collide with a KOReader session that
# happened to start at the same instant.
WEB_READER_DEVICE_ID = "crossbill-web-reader"


class SaveReadingPositionUseCase:
    """Store a reading position from the browser, and keep its reading session going.

    Two things happen on every write, and only the second is at all subtle.

    **The position is converted and stored.** The locator the navigator produced
    is resolved back to the canonical KOReader xpointer (ADR-0004 §2), graded,
    and rejected below :data:`MINIMUM_POSITION_CONFIDENCE`; the xpointer is then
    resolved to a ``Position`` through the book's index. The locator itself is
    kept beside them so the browser can be put back exactly where it was.

    **A real reading session is written.** Web reading produces the same
    ``reading_sessions`` rows an e-reader's sync does, which is what lets the
    progress bar and ``ReadingStatisticsCalculator`` understand it without
    knowing it exists (ADR-0004, Amendment 3). The first write after opening a
    book starts a session; each one after that extends it. A gap longer than
    ``WEB_READING_SESSION_IDLE_SECONDS`` starts a new one instead, and a reader
    who closes the book ends theirs by saying so.

    Nothing runs in the background to close a session. A session's end is the
    last position it was told about, so one that stops being extended is already
    over -- which is also why a tab left open overnight records no reading.
    """

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        position_repository: WebReadingPositionRepositoryProtocol,
        session_repository: ReadingSessionRepositoryProtocol,
        position_anchor_service: PositionAnchorServiceProtocol,
        book_position_index: BookPositionIndexProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.position_repository = position_repository
        self.session_repository = session_repository
        self.position_anchor_service = position_anchor_service
        self.book_position_index = book_position_index
        self.idle_seconds = get_settings().WEB_READING_SESSION_IDLE_SECONDS

    async def save_reading_position(
        self,
        book_id: int,
        user_id: int,
        locator: Locator,
        stored_locator: Mapping[str, Any],
        recorded_at: datetime,
        closing: bool = False,
    ) -> WebReadingPosition:
        """Record the reader's position, returning what is now stored for the book.

        Args:
            book_id: The book being read.
            user_id: Whose reading this is.
            locator: The position, with hrefs already read back into the paths
                the publication uses internally.
            stored_locator: The same position as the browser sent it, kept
                verbatim so that handing it back needs no second translation.
            recorded_at: When the reader was there, by their own clock. Clamped
                to now, because a clock that is ahead must not invent reading
                time it can then be credited with.
            closing: Whether the reader is leaving the book. The position is
                stored and the session extended either way; this only says the
                session is finished, so the next one starts fresh.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no EPUB to place a position in.
            UnresolvablePositionError: If the locator cannot be placed in the
                book, or only weakly.
        """
        user = UserId(user_id)
        book = await self.book_repository.find_by_id(BookId(book_id), user)
        if book is None:
            raise BookNotFoundError(book_id)
        if not book.ebook_file:
            raise EbookFileNotFoundError(book_id)

        observed_at = min(as_aware(recorded_at), datetime.now(UTC))
        stored = await self.position_repository.find_for_book(BookId(book_id), user)
        # A write that has nothing new to say is answered with what is stored
        # rather than refused: the unload beacon and an ordinary write race by
        # design, and the loser is not an error.
        if stored is not None and not stored.is_newer_than_stored(observed_at):
            return stored

        xpoint = await self._canonical_position(book.ebook_file, locator)
        position = await self._resolve_position(book, xpoint)
        session_id = await self._continue_session(book, user, stored, xpoint, position, observed_at)

        if stored is None:
            stored = WebReadingPosition.create(
                user_id=user,
                book_id=BookId(book_id),
                locator=stored_locator,
                xpoint=xpoint,
                observed_at=observed_at,
                position=position,
                reading_session_id=session_id,
            )
        else:
            stored.record(
                locator=stored_locator,
                xpoint=xpoint,
                observed_at=observed_at,
                position=position,
                reading_session_id=session_id,
            )
        if closing:
            stored.close_session()
        return await self.position_repository.save(stored)

    async def _canonical_position(self, ebook_file: str, locator: Locator) -> XPoint:
        """Convert a browser locator to the stored position format, or refuse it.

        A reading position is a caret rather than a selection, so only the start
        of the resolved range means anything; the range is what the port speaks
        in because a highlight needs both ends.
        """
        try:
            match = await self.position_anchor_service.xpoint_range_for_locator(ebook_file, locator)
        except AnchorResolutionError as exc:
            raise UnresolvablePositionError(str(exc)) from exc

        if match.confidence < MINIMUM_POSITION_CONFIDENCE:
            logger.info(
                "rejected_weak_reading_position",
                href=locator.href,
                confidence=match.confidence.name,
                floor=MINIMUM_POSITION_CONFIDENCE.name,
            )
            raise UnresolvablePositionError(
                f"the quote matched too weakly ({match.confidence.name})"
            )
        return match.xpoints.start

    async def _resolve_position(self, book: Book, xpoint: XPoint) -> Position | None:
        """Place the xpointer in document order, or leave the progress unknown.

        Backfills the book's own end position on the way past, exactly as the
        KOReader upload path does and for the same reason: progress is a
        fraction of that number, and a book whose EPUB predates it has none.
        Reading a book in the browser is as good an occasion to learn how long
        it is as syncing one from an e-reader.
        """
        if not book.ebook_file:
            return None
        index = await self.book_position_index.position_index_for(book.ebook_file)
        if index is None:
            return None
        if book.end_position is None and index.total_elements > 0:
            book.update_end_position(Position(index=index.total_elements, char_index=0))
            await self.book_repository.save(book)
        return index.resolve(xpoint.to_string())

    async def _continue_session(
        self,
        book: Book,
        user_id: UserId,
        stored: WebReadingPosition | None,
        xpoint: XPoint,
        position: Position | None,
        observed_at: datetime,
    ) -> ReadingSessionId:
        """Extend the sitting this position belongs to, or begin a new one."""
        open_session = await self._open_session(stored, user_id, observed_at)
        if open_session is None:
            session = ReadingSession.create(
                user_id=user_id,
                book_id=book.id,
                start_time=observed_at,
                end_time=observed_at,
                start_xpoint=XPointRange(start=xpoint, end=xpoint),
                start_position=position,
                end_position=position,
                device_id=WEB_READER_DEVICE_ID,
            )
        else:
            session = open_session
            session.extend_to(observed_at, xpoint=xpoint, position=position)
        return (await self.session_repository.save(session)).id

    async def _open_session(
        self,
        stored: WebReadingPosition | None,
        user_id: UserId,
        observed_at: datetime,
    ) -> ReadingSession | None:
        """The session this write continues, if there is still one to continue.

        ``None`` when the reader has never read this book here, when they closed
        it last time, when the session has since been deleted, or when nothing
        has been heard for long enough that this is a new sitting.

        The gap is measured from the session's own end rather than from the
        stored position, so that a session is judged on when it was really last
        extended.
        """
        if stored is None or stored.reading_session_id is None:
            return None
        session = await self.session_repository.find_by_id(stored.reading_session_id, user_id)
        if session is None:
            return None
        gap = (observed_at - as_aware(session.end_time)).total_seconds()
        return None if gap > self.idle_seconds else session
