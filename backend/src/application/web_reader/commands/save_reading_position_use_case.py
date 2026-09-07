"""Record where a reader has got to in a book they are reading in the browser."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import structlog

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.reading_session_repository import (
    ReadingSessionRepositoryProtocol,
)
from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorResolutionError,
    AnchorSource,
    Locator,
)
from src.application.web_reader.devices import WEB_READER_DEVICE_ID
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

# The weakest match this will store a position from -- one floor per kind of
# anchor, because the three are not points on one scale (ADR-0004, Amendment 3).
#
# **A quote** is graded on evidence the browser supplied, which is what
# ADR-0004 §5's floor is about, and HIGHLIGHT_ONLY is where "we know which place
# this is" begins. The two grades below it are the two that mean the opposite:
# FUZZY is the quote not being in the book as written -- the shape a replaced,
# differently typeset EPUB takes -- and AMBIGUOUS is the quote being in several
# places with neither context settling which. That is deliberately one grade
# below what a *highlight* will demand (M4.1): a highlight drawn in the wrong
# paragraph is a visible, lasting falsehood about what the reader marked, while
# a reading position that is off costs a moment finding one's place.
#
# **An element** names exactly one place in the document, which is the same
# standard of evidence as a quote occurring exactly once, so it meets the same
# floor and is capped there.
#
# **A progression** is approximate by construction and is accepted anyway --
# and this is the load-bearing choice, because it is what almost every real
# reading position turns out to be. A page turn in a reflowable book reaches
# the server as an href and a fraction and nothing else, so a floor that
# refused it would refuse to record reading at all. What still refuses is the
# conversion failing outright, which is the signal §5 actually cares about: a
# locator naming a resource the book does not have is an EPUB that has been
# replaced, and that is an error rather than an approximation.
MINIMUM_CONFIDENCE = {
    AnchorSource.QUOTE: AnchorConfidence.HIGHLIGHT_ONLY,
    AnchorSource.ELEMENT: AnchorConfidence.HIGHLIGHT_ONLY,
    AnchorSource.PROGRESSION: AnchorConfidence.FUZZY,
}


# How far back a reader may jump and still be in the same sitting, as a fraction
# of the book.
#
# A sitting reports the ground it covered -- its page range and its xpoint range
# keep the furthest they reached -- while its `end_position` keeps where the
# reader is. Those two only agree while the reader is moving through the book.
# Somebody who starts a novel again from the beginning half an hour after
# finishing it would otherwise be one sitting that reports three hundred pages
# read and a progress bar on page one.
#
# A quarter of a book is not a sequence of page turns; it is navigation -- a
# contents link, a bookmark, starting again. Re-reading the previous chapter,
# which is the largest backward move ordinary reading makes, is a few per cent
# of a book of ordinary length and sits comfortably inside it. Erring low would
# split a sitting that re-read a long chapter; erring high leaves the phantom
# pages this exists to stop, so the threshold sits nearer the cautious end than
# the middle.
SAME_SITTING_BACKWARD_FRACTION = 0.25


def _has_restarted(session: ReadingSession, book: Book, position: Position | None) -> bool:
    """Whether this position is too far behind the sitting to belong to it.

    Measured against the book's own length, so "far" means the same thing in a
    novel and in a pamphlet. Unknowable -- and so ``False`` -- when either end
    of the comparison is missing: a book whose length was never established
    cannot say what a quarter of it is, and a position that did not resolve says
    nothing about where the reader went.
    """
    if position is None or session.end_position is None or book.end_position is None:
        return False
    length = book.end_position.index
    if length <= 0:
        return False
    jumped_back = session.end_position.index - position.index
    return jumped_back > length * SAME_SITTING_BACKWARD_FRACTION


def _page(locator: Locator) -> int | None:
    """The synthetic page a locator says it is on, if it says a usable one.

    ``locations.position`` indexes the position list *this API served the
    reader*, and it is the number their own chrome counts "Page X of N" from --
    so a session filled from it reports the pages they watched go by, and reads
    the same as a session synced from an e-reader, whose pages are that
    device's own pagination.

    A number outside the 1-based list Readium defines is treated as absent
    rather than refused: the position itself is already stored and correct, and
    a page range is what a session is *labelled* with. Degrading it costs a line
    on a card; failing the write would cost the reading.
    """
    position = locator.locations.position
    return position if position is not None and position > 0 else None


class SaveReadingPositionUseCase:
    """Store a reading position from the browser, and keep its reading session going.

    Two things happen on every write, and only the second is at all subtle.

    **The position is converted and stored.** The locator the navigator produced
    is resolved back to the canonical KOReader xpointer (ADR-0004 §2), graded,
    and rejected below the :data:`MINIMUM_CONFIDENCE` its kind of anchor has
    to clear; the xpointer is then
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
        now: datetime,
        closing: bool = False,
    ) -> WebReadingPosition:
        """Record the reader's position, returning what is now stored for the book.

        The order of the two writes is the whole of the concurrency story. The
        position is claimed first, in one conditional upsert, and the reading
        session is written only by the request that won that claim -- so no
        session row can be left behind by a position write that did not happen,
        and two tabs turning pages cannot collide into a duplicate-key error.
        The session pointer is then attached under the same claim, so a write
        that has since been overtaken quietly changes nothing.

        Args:
            book_id: The book being read.
            user_id: Whose reading this is.
            locator: The position, with hrefs already read back into the paths
                the publication uses internally.
            stored_locator: The same position as the browser sent it, kept
                verbatim so that handing it back needs no second translation.
            recorded_at: When the reader was at this position, by their own
                clock. Decides whether the write *moves* the stored position and
                nothing else -- never how long anybody read, and never which of
                two writes is later. Never read as later than ``now``.
            now: The server's clock, read once at the edge. Decides which of two
                writes is later, and is the only clock a reading session is
                measured on, so no client can be credited with time it did not
                spend.
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

        xpoint = await self._canonical_position(book.ebook_file, locator)
        position = await self._resolve_position(book, xpoint)

        recorded = await self.position_repository.record(
            WebReadingPosition.create(
                user_id=user,
                book_id=BookId(book_id),
                locator=stored_locator,
                xpoint=xpoint,
                written_at=now,
                recorded_at=min(as_aware(recorded_at), now),
                position=position,
            )
        )
        # Overtaken. Answered with what is stored rather than refused: the write
        # a closing tab sends and the one a page turn sends race by design, and
        # the loser is not an error. Nothing has been written, and in particular
        # no reading session has been touched.
        if recorded is None:
            stored = await self.position_repository.find_for_book(BookId(book_id), user)
            if stored is not None:
                return stored
            raise UnresolvablePositionError("the position was overtaken and then removed")

        # Only a write that moved the position says anything about *where* the
        # reader is; one that did not still says they are here, which is what
        # extends the sitting. Passing the stale position on would drag the
        # session's progress back to a page another tab left an hour ago.
        session_id = await self._continue_session(
            book=book,
            user_id=user,
            was_open=recorded.was_open,
            now=now,
            xpoint=xpoint if recorded.advanced else None,
            position=position if recorded.advanced else None,
            page=_page(locator) if recorded.advanced else None,
        )
        await self.position_repository.attach_session(
            recorded.position, None if closing else session_id, now
        )
        return recorded.position

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

        floor = MINIMUM_CONFIDENCE[match.anchored_by]
        if match.confidence < floor:
            logger.info(
                "rejected_weak_reading_position",
                href=locator.href,
                anchored_by=match.anchored_by.value,
                confidence=match.confidence.name,
                floor=floor.name,
            )
            raise UnresolvablePositionError(
                f"the {match.anchored_by.value} matched too weakly ({match.confidence.name})"
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
        was_open: ReadingSessionId | None,
        now: datetime,
        xpoint: XPoint | None,
        position: Position | None,
        page: int | None,
    ) -> ReadingSessionId | None:
        """Extend the sitting this position belongs to, or begin a new one.

        ``None`` when there is nothing to record: a write that moved no position
        and found no sitting open is a tab closing on a page another tab has
        long since left, and a sitting of its own would be a fiction.
        """
        open_session = await self._open_session(was_open, user_id, now, book, position)
        if open_session is None:
            if xpoint is None:
                return None
            session = ReadingSession.create(
                user_id=user_id,
                book_id=book.id,
                start_time=now,
                end_time=now,
                start_xpoint=XPointRange(start=xpoint, end=xpoint),
                start_position=position,
                end_position=position,
                start_page=page,
                end_page=page,
                device_id=WEB_READER_DEVICE_ID,
            )
        else:
            session = open_session
            # Never before the sitting began. The moment comes from the reader's
            # clock, and a second device a few minutes slow would otherwise
            # offer one earlier than the session it is joining -- which is not a
            # reader who read backwards, it is two clocks disagreeing, and the
            # session is the wrong place to find out about it.
            session.extend_to(now, xpoint=xpoint, position=position, page=page)
        return (await self.session_repository.save(session)).id

    async def _open_session(
        self,
        was_open: ReadingSessionId | None,
        user_id: UserId,
        now: datetime,
        book: Book,
        position: Position | None,
    ) -> ReadingSession | None:
        """The session this write continues, if there is still one to continue.

        ``None`` when the reader has never read this book here, when they closed
        it last time, when the session has since been deleted, when nothing has
        been heard for long enough that this is a new sitting, or when the
        reader has jumped back far enough that this is a new one anyway.

        The gap is measured from the session's own end rather than from the
        stored position, so that a session is judged on when it was really last
        extended.
        """
        if was_open is None:
            return None
        session = await self.session_repository.find_by_id(was_open, user_id)
        if session is None:
            return None
        gap = (now - as_aware(session.end_time)).total_seconds()
        if gap > self.idle_seconds:
            return None
        return None if _has_restarted(session, book, position) else session
