"""Read use case behind the reading-position endpoint: where does this book open?"""

import structlog

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.reading_session_repository import (
    ReadingSessionRepositoryProtocol,
)
from src.application.web_reader.anchors import AnchorResolutionError
from src.application.web_reader.devices import WEB_READER_DEVICE_ID
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.application.web_reader.protocols.web_reading_position_repository import (
    WebReadingPositionRepositoryProtocol,
)
from src.application.web_reader.queries.resume_position import (
    NOWHERE,
    ResumePosition,
    ResumeSource,
)
from src.domain.common.time import as_aware
from src.domain.common.value_objects import BookId, UserId, XPoint
from src.domain.library.entities.book import Book
from src.domain.reading.entities.reading_session import ReadingSession
from src.domain.reading.exceptions import BookNotFoundError
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition

logger = structlog.get_logger(__name__)


class GetResumePositionUseCase:
    """Answer where the web reader should open a book, across every device.

    The browser is not the only reader. Somebody who read three chapters on
    their e-reader last night and then opens the book here expects to be where
    they left off, and the row the browser wrote last week is not that place. So
    two candidates are weighed and the later one wins:

    1. **The stored web position**, at its own ``recorded_at`` -- the reader's
       clock at the moment they were there. It carries the locator verbatim,
       which is the best answer there is: no conversion, no approximation.
    2. **The end of the latest reading session another device wrote**, at its
       ``end_time``. Only an xpointer was ever stored for it (ADR-0004 §1), so a
       locator has to be derived from the EPUB on the way out -- the forward
       direction of the anchor port, which nothing has used server-side until
       now.

    **Sessions the web reader itself wrote are left out of (2) entirely**, and
    that is the whole of the dedupe. A web session and the web position row are
    written by the same request about the same moment, so such a session never
    adds information -- but it would frequently *win*, because its ``end_time``
    is the server's clock while the position's ``recorded_at`` is the reader's,
    and a reader a minute behind would have their exact stored locator thrown
    over in favour of one re-derived from the xpointer beside it. Same place,
    strictly worse answer. What (2) is for is the reading this browser did not
    do.

    Ties go to the web position for the same reason: an exact locator beats a
    derived one at equal freshness.

    **A conversion that fails is reported, not raised.** An xpointer that no
    longer resolves is the shape a replaced EPUB takes (ADR-0004 §5), and the
    honest answer to "where does this book open" is then *at the beginning, and
    your place was lost* -- which the reader can only say if the response
    distinguishes it from a book nobody has ever read.

    Nothing is written here. A reading session that has stopped being extended
    is already over (ADR-0004, Amendment 3), so there is no idle session for a
    read to have to close.
    """

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        position_repository: WebReadingPositionRepositoryProtocol,
        session_repository: ReadingSessionRepositoryProtocol,
        position_anchor_service: PositionAnchorServiceProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.position_repository = position_repository
        self.session_repository = session_repository
        self.position_anchor_service = position_anchor_service

    async def get_resume_position(self, book_id: int, user_id: int) -> ResumePosition:
        """Return where to open this book, or :data:`NOWHERE` if it has never been read.

        The book is looked up first so that "this book is not yours" stays a
        404, as it is everywhere else in the library, rather than reading as a
        book nobody has opened yet.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        book = await self.book_repository.find_by_id(BookId(book_id), UserId(user_id))
        if book is None:
            raise BookNotFoundError(book_id)

        stored = await self.position_repository.find_for_book(BookId(book_id), UserId(user_id))
        elsewhere = _left_off_at(
            await self.session_repository.find_latest_ended(
                BookId(book_id), UserId(user_id), excluding_device_id=WEB_READER_DEVICE_ID
            )
        )
        if elsewhere is None:
            return _from_stored(stored)
        session, xpoint = elsewhere
        # Both moments are a reader's own clock saying when they were at a
        # place, which is the only comparison available: arrival at this server
        # is not a fact about a KOReader session at all, since one is uploaded
        # whenever the device next syncs. A tie goes to the stored locator,
        # which is exact where a derived one is reconstructed.
        if stored is not None and as_aware(stored.recorded_at) >= as_aware(session.end_time):
            return _from_stored(stored)
        return await self._from_session(book, session, xpoint)

    async def _from_session(
        self, book: Book, session: ReadingSession, xpoint: XPoint
    ) -> ResumePosition:
        """Derive a locator for where another device left off, or report that it is lost."""
        answer = ResumePosition(
            source=ResumeSource.KOREADER,
            xpoint=xpoint,
            position=session.end_position,
            recorded_at=as_aware(session.end_time),
        )
        if not book.ebook_file:
            return answer
        try:
            derived = await self.position_anchor_service.locator_for_xpoint(book.ebook_file, xpoint)
        except AnchorResolutionError as exc:
            # Not raised: a derivation failure loses a *view* of a position
            # whose canonical xpointer is still safely stored, and the reader is
            # better served by opening at the beginning and being told why.
            logger.info(
                "unresolvable_resume_position",
                book_id=book.id.value,
                xpoint=xpoint.to_string(),
                reason=str(exc),
            )
            return answer
        return ResumePosition(
            source=answer.source,
            derived_locator=derived,
            xpoint=answer.xpoint,
            position=answer.position,
            recorded_at=answer.recorded_at,
        )


def _left_off_at(session: ReadingSession | None) -> tuple[ReadingSession, XPoint] | None:
    """A session together with where it ended, when it recorded a usable xpointer.

    A session's boundaries are stored as a pair of columns and read back as one
    ``XPointRange``, so a session missing either end -- which a KOReader upload
    without positions is -- has none at all and cannot say where to resume.
    Such a session is no candidate, however recent it is.
    """
    if session is None or session.start_xpoint is None:
        return None
    return session, session.start_xpoint.end


def _from_stored(stored: WebReadingPosition | None) -> ResumePosition:
    """The browser's own last position, handed back exactly as it was written."""
    if stored is None:
        return NOWHERE
    return ResumePosition(
        source=ResumeSource.WEB,
        stored_locator=stored.locator,
        xpoint=stored.xpoint,
        position=stored.position,
        recorded_at=as_aware(stored.recorded_at),
    )
