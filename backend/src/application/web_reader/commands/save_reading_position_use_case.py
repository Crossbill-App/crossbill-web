"""Record where a reader has got to in a book they are reading in the browser."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog

from src.application.library.commands.book_files.backfill_book_length import backfill_book_length
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.library.protocols.position_index_service import PositionIndexServiceProtocol
from src.application.reading.page_view_placement import place_page_view
from src.application.reading.protocols.reading_session_repository import (
    ReadingSessionRepositoryProtocol,
)
from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorMatch,
    AnchorNotFoundError,
    AnchorResolutionError,
    AnchorSource,
    Locator,
)
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.application.web_reader.protocols.web_reading_position_repository import (
    WebReadingPositionRepositoryProtocol,
)
from src.application.web_reader.publications import epub_content_hash
from src.config import get_settings
from src.domain.common.devices import WEB_READER_DEVICE_ID
from src.domain.common.time import as_aware
from src.domain.common.value_objects import BookId, ReadingSessionId, UserId, XPoint, XPointRange
from src.domain.common.value_objects.position import Position
from src.domain.common.value_objects.position_index import PositionIndex
from src.domain.library.entities.book import Book
from src.domain.library.exceptions import EbookFileNotFoundError
from src.domain.reading.entities.reading_session import ReadingSession
from src.domain.reading.exceptions import BookNotFoundError, ReadingSessionNotFoundError
from src.domain.reading.value_objects.page_view import PageView
from src.domain.web_reader.entities.web_reading_position import WebReadingPosition
from src.domain.web_reader.exceptions import BookFileUnreadableError, UnresolvablePositionError

logger = structlog.get_logger(__name__)

# The weakest match this will store a position from, one floor per kind of anchor.
#
# A quote or an element has to land in one place, and the grades below HIGHLIGHT_ONLY
# say it did not: the text is not in the book as written, or it is in several places
# and neither side of it settles which.
#
# A progression can only ever be approximate, and is taken anyway. That is the choice
# that matters: a page turn in a reflowable book arrives as an href and a fraction and
# nothing else, so refusing those would refuse to record reading at all. A conversion
# that fails outright is still refused.
MINIMUM_CONFIDENCE = {
    AnchorSource.QUOTE: AnchorConfidence.HIGHLIGHT_ONLY,
    AnchorSource.ELEMENT: AnchorConfidence.HIGHLIGHT_ONLY,
    AnchorSource.PROGRESSION: AnchorConfidence.FUZZY,
}

# How far back a reader may jump and still be in the same sitting, as a fraction of
# the book.
#
# A sitting reports the ground it covered, while its end_position says where the reader
# is. Those only agree while the reader is going forwards: somebody who starts a novel
# again half an hour after finishing it would otherwise be one sitting that claims three
# hundred pages, with the progress bar back on page one. Nobody pages back a quarter of a
# book -- they follow a link or a bookmark -- and a quarter still leaves room to re-read
# the longest chapter.
SAME_SITTING_BACKWARD_FRACTION = 0.25

# A Page View is counted in characters, which a progression only approximates
# (ADR-0004, Amendment 9).
PAGE_VIEW_ANCHORS = {AnchorSource.QUOTE, AnchorSource.ELEMENT}


@dataclass(frozen=True)
class PageViewReport:
    """One screen the Web Reader showed, as it reports it: the text at either edge, and when."""

    start: Locator
    end: Locator
    shown_ms_before_send: int
    duration_ms: int


class _UnplaceablePageViewError(Exception):
    pass


@dataclass(frozen=True)
class _Reached:
    """Where a write that moved the stored position, or opened the book, says the reader is."""

    xpoint: XPoint
    locator: Locator
    position: Position | None
    page: int | None


def _firmly_anchored(match: AnchorMatch | None) -> AnchorMatch:
    if match is None:
        raise _UnplaceablePageViewError("not_in_book")
    if match.anchored_by not in PAGE_VIEW_ANCHORS:
        raise _UnplaceablePageViewError(f"anchored_by_{match.anchored_by.value}")
    if match.confidence < MINIMUM_CONFIDENCE[match.anchored_by]:
        raise _UnplaceablePageViewError("weak_anchor")
    return match


def _page_view(
    report: PageViewReport,
    start: AnchorMatch | None,
    end: AnchorMatch | None,
    position_index: PositionIndex,
    source_hash: str,
    now: datetime,
) -> PageView:
    first_words = _firmly_anchored(start).xpoints.start
    last_words = _firmly_anchored(end).xpoints.end
    if report.shown_ms_before_send < 0 or report.duration_ms < 0:
        raise _UnplaceablePageViewError("negative_time")
    try:
        shown_at = now - timedelta(milliseconds=report.shown_ms_before_send)
        duration = timedelta(milliseconds=report.duration_ms)
    except OverflowError as exc:
        raise _UnplaceablePageViewError("time_out_of_range") from exc
    page_view = place_page_view(
        position_index,
        first_words.to_string(),
        last_words.to_string(),
        source_hash,
        shown_at=shown_at,
        duration=duration,
    )
    if page_view is None:
        raise _UnplaceablePageViewError("not_in_position_index")
    return page_view


def _drop_unfitted(book_id: BookId, page_views: list[PageView]) -> None:
    for page_view in page_views:
        logger.warning(
            "dropping_page_view",
            book_id=book_id.value,
            reason="outside_session",
            shown_at=page_view.shown_at,
        )


def _record_page_views(
    book_id: BookId, session: ReadingSession, page_views: list[PageView]
) -> None:
    _drop_unfitted(book_id, session.record_page_views(page_views))


def _has_restarted(session: ReadingSession, book: Book, position: Position | None) -> bool:
    """Whether this position is too far behind the sitting to belong to it.

    Measured against the book's own length, so "far" means the same in a novel and in
    a pamphlet, and unknowable -- so ``False`` -- when either end of the comparison is
    missing.
    """
    if position is None or session.end_position is None or book.end_position is None:
        return False
    length = book.end_position.index
    if length <= 0:
        return False
    jumped_back = session.end_position.index - position.index
    return jumped_back > length * SAME_SITTING_BACKWARD_FRACTION


def _begun_at(book_id: BookId, user_id: UserId, now: datetime, reached: _Reached) -> ReadingSession:
    return ReadingSession.create(
        user_id=user_id,
        book_id=book_id,
        start_time=now,
        end_time=now,
        # Seeded here or never: a session that opened without a range can never be
        # given one.
        start_xpoint=XPointRange(start=reached.xpoint, end=reached.xpoint),
        start_position=reached.position,
        end_position=reached.position,
        start_page=reached.page,
        end_page=reached.page,
        device_id=WEB_READER_DEVICE_ID,
    )


class SaveReadingPositionUseCase:
    """Store a reading position from the browser, and keep its reading session going.

    The locator the navigator produced is resolved back to the canonical KOReader
    xpointer (ADR-0004 §2), graded against :data:`MINIMUM_CONFIDENCE`, and kept beside
    it so the browser can be put back exactly where it was.

    A real ``reading_sessions`` row is written too, which is what lets browser reading
    reach the progress bar and the reading statistics without either knowing the web
    reader exists (ADR-0004, Amendments 3 and 10). Opening the book starts a sitting,
    each write after that extends it, a gap longer than
    ``WEB_READING_SESSION_IDLE_SECONDS`` starts a new one, and a reader who closes the
    book ends theirs by saying so -- which deletes it if it fails the filters a
    KOReader session must pass to be stored.
    """

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
        position_repository: WebReadingPositionRepositoryProtocol,
        session_repository: ReadingSessionRepositoryProtocol,
        position_anchor_service: PositionAnchorServiceProtocol,
        file_repository: FileRepositoryProtocol,
        position_index_service: PositionIndexServiceProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.chapter_repository = chapter_repository
        self.position_repository = position_repository
        self.session_repository = session_repository
        self.position_anchor_service = position_anchor_service
        self.file_repository = file_repository
        self.position_index_service = position_index_service
        settings = get_settings()
        self.idle_seconds = settings.WEB_READING_SESSION_IDLE_SECONDS
        self.minimum_duration = timedelta(seconds=settings.MINIMUM_READING_SESSION_DURATION)

    async def save_reading_position(
        self,
        book_id: int,
        user_id: int,
        locator: Locator,
        stored_locator: Mapping[str, Any],
        recorded_at: datetime,
        now: datetime,
        page_views: list[PageViewReport],
        page: int | None = None,
        opening: bool = False,
        closing: bool = False,
    ) -> WebReadingPosition:
        """Record the reader's position, returning what is now stored for the book.

        The order of the two writes is the whole of the concurrency story. The
        position is claimed first, in one conditional upsert, and the reading session
        is written only by the request that won that claim -- so no session row can be
        left behind by a position write that did not happen. The session pointer is
        attached under the same claim, so a write since overtaken changes nothing.

        Args:
            book_id: The book being read.
            user_id: Whose reading this is.
            locator: The position, with hrefs already read back into the paths the
                publication uses internally.
            stored_locator: The same position as the browser sent it, kept verbatim so
                that handing it back needs no second translation.
            recorded_at: When the reader was at this position, by their own clock.
                Decides whether the write *moves* the stored position and nothing
                else. Clamped to ``now``, so a clock running fast wins the current
                race rather than freezing the position until it catches up -- which
                also bounds how much the idle-tab protection a client clock can
                defeat is worth.
            now: The server's clock, read once at the edge. Decides which of two
                writes is later, and is the only clock a reading session is measured
                on, so no client can be credited with time it did not spend.
            page_views: The screens shown since the last accepted write. Each goes to
                the session it fits, and one that cannot be placed is dropped.
            page: The synthetic page the reader is shown, if their navigator counts
                one; what the sitting's page range is labelled with.
            opening: Whether the book has just been opened at this position. Starts a
                new sitting whether or not the position moved.
            closing: Whether the reader is leaving the book. The position is stored and
                the session extended either way; this ends the sitting, and deletes it
                if it is too short or never moved.

        Raises:
            BookNotFoundError: If the user has no such book.
            EbookFileNotFoundError: If the book has no EPUB to place a position in.
            UnresolvablePositionError: If the EPUB does not hold the place the locator
                names, or holds it too weakly.
            BookFileUnreadableError: If the stored EPUB cannot be read at all.
        """
        user = UserId(user_id)
        book = await self.book_repository.find_by_id(BookId(book_id), user)
        if book is None:
            raise BookNotFoundError(book_id)
        epub_content = await self.file_repository.get_epub(book.ebook_file)
        if not epub_content:
            raise EbookFileNotFoundError(book_id)

        source_hash = epub_content_hash(epub_content)
        xpoint = await self._canonical_position(book.id, epub_content, locator)
        position_index = await self._position_index(book, epub_content)
        position = position_index.resolve(xpoint.to_string())
        placed = await self._placed_page_views(
            book.id, epub_content, position_index, source_hash, now, page_views
        )

        recorded = await self.position_repository.record(
            WebReadingPosition.create(
                user_id=user,
                book_id=book.id,
                locator=stored_locator,
                xpoint=xpoint,
                locator_source_hash=source_hash,
                written_at=now,
                recorded_at=min(as_aware(recorded_at), now),
                position=position,
            )
        )
        if recorded is None:
            # Overtaken, and so answered with what is stored rather than refused: the
            # write a closing tab sends and the one a page turn sends race by design.
            # Its Page Views still go to the session the stored position points at,
            # which is otherwise left alone.
            stored = await self.position_repository.find_for_book(book.id, user)
            if stored is None:
                raise UnresolvablePositionError("the position was overtaken and then removed")
            await self._add_to_stored_session(book.id, user, stored.reading_session_id, placed)
            return stored

        # Only a write that moved the position says anything about *where* the reader
        # is; one that did not still says they are here, which is what extends the
        # sitting. Passing the stale position on would drag the session's progress back
        # to a page another tab left an hour ago. An opening write says where its own
        # sitting begins, whichever tab is further on.
        reached = (
            _Reached(xpoint, locator, position, page) if recorded.advanced or opening else None
        )
        session = await self._continue_session(
            book=book,
            user_id=user,
            was_open=None if opening else recorded.position.reading_session_id,
            now=now,
            reached=reached,
            page_views=placed,
        )
        session_id = await self._store_session(session, closing, reached, source_hash)
        await self.position_repository.attach_session(
            recorded.position, None if closing else session_id
        )
        return recorded.position

    async def _canonical_position(
        self, book_id: BookId, epub_content: bytes, locator: Locator
    ) -> XPoint:
        """Convert a browser locator to the stored position format, or refuse it.

        A reading position is a caret rather than a selection, so only the start of
        the resolved range means anything; the range is what the port speaks in
        because a highlight needs both ends.
        """
        try:
            match = await self.position_anchor_service.xpoint_range_for_locator(
                epub_content, locator
            )
        # The subclass first: one place the book does not hold is the writer's
        # problem, where an archive that cannot be read is the book's.
        except AnchorNotFoundError as exc:
            raise UnresolvablePositionError(str(exc)) from exc
        except AnchorResolutionError as exc:
            raise BookFileUnreadableError(str(exc)) from exc

        floor = MINIMUM_CONFIDENCE[match.anchored_by]
        if match.confidence < floor:
            logger.info(
                "rejected_weak_reading_position",
                book_id=book_id.value,
                href=locator.href,
                anchored_by=match.anchored_by.value,
                confidence=match.confidence.name,
                floor=floor.name,
            )
            raise UnresolvablePositionError(
                f"the {match.anchored_by.value} matched too weakly ({match.confidence.name})"
            )
        return match.xpoints.start

    async def _position_index(self, book: Book, epub_content: bytes) -> PositionIndex:
        """Index the book in document order, learning its length on the way.

        Progress is a fraction of that length, and a book uploaded before the column
        existed has none; the KOReader upload path backfills it for the same reason.
        """
        # Off the event loop: an index is lxml over every document of the book, and
        # this runs on every page turn.
        index = await asyncio.to_thread(
            self.position_index_service.build_position_index, epub_content
        )
        await backfill_book_length(book, index, self.book_repository, self.chapter_repository)
        return index

    async def _placed_page_views(
        self,
        book_id: BookId,
        epub_content: bytes,
        position_index: PositionIndex,
        source_hash: str,
        now: datetime,
        reports: list[PageViewReport],
    ) -> list[PageView]:
        if not reports:
            return []
        edges: dict[tuple[int, str], Locator] = {}
        for n, report in enumerate(reports):
            edges[(n, "start")] = report.start
            edges[(n, "end")] = report.end
        try:
            matches = await self.position_anchor_service.xpoint_ranges_for_locators(
                epub_content, edges
            )
        except AnchorResolutionError as exc:
            logger.warning(
                "dropping_page_views", book_id=book_id.value, count=len(reports), reason=str(exc)
            )
            return []
        placed: list[PageView] = []
        for n, report in enumerate(reports):
            try:
                placed.append(
                    _page_view(
                        report,
                        matches[(n, "start")],
                        matches[(n, "end")],
                        position_index,
                        source_hash,
                        now,
                    )
                )
            except _UnplaceablePageViewError as exc:
                logger.warning("dropping_page_view", book_id=book_id.value, reason=str(exc))
        return placed

    async def _add_to_stored_session(
        self,
        book_id: BookId,
        user_id: UserId,
        session_id: ReadingSessionId | None,
        page_views: list[PageView],
    ) -> None:
        if not page_views:
            return
        session = (
            await self.session_repository.find_by_id(session_id, user_id)
            if session_id is not None
            else None
        )
        if session is None:
            logger.warning(
                "dropping_page_views",
                book_id=book_id.value,
                count=len(page_views),
                reason="no_session",
            )
            return
        _record_page_views(book_id, session, page_views)
        await self.session_repository.add_page_views(session)

    async def _continue_session(
        self,
        book: Book,
        user_id: UserId,
        was_open: ReadingSessionId | None,
        now: datetime,
        reached: _Reached | None,
        page_views: list[PageView],
    ) -> ReadingSession | None:
        """The sitting this position belongs to, extended to it or begun at it.

        A jump back saves the sitting it leaves, extended to the jump and holding the
        write's Page Views, before beginning the next. After an idle gap the old sitting
        keeps the Page Views that fit it, unextended. ``None`` when there is nothing to
        record: a write that moved no position and found no sitting open is a tab
        closing on a page another tab has long since left, and a sitting of its own
        would be a fiction.
        """
        leftovers = page_views
        last = await self._last_session(was_open, user_id)
        if last is not None and not self._has_gone_idle(last, now):
            position = reached.position if reached else None
            if not _has_restarted(last, book, position):
                last.extend_to(
                    now,
                    xpoint=reached.xpoint if reached else None,
                    position=position,
                    page=reached.page if reached else None,
                )
                _record_page_views(book.id, last, page_views)
                return last
            # The old sitting ran until the jump, but did not reach where it landed.
            last.extend_to(now)
            _record_page_views(book.id, last, page_views)
            await self._save_if_still_there(last)
            leftovers = []
        elif last is not None:
            leftovers = last.record_page_views(page_views)
            await self.session_repository.add_page_views(last)

        if reached is None:
            _drop_unfitted(book.id, leftovers)
            return None
        session = _begun_at(book.id, user_id, now, reached)
        _record_page_views(book.id, session, leftovers)
        return session

    async def _store_session(
        self,
        session: ReadingSession | None,
        closing: bool,
        reached: _Reached | None,
        source_hash: str,
    ) -> ReadingSessionId | None:
        """Save the sitting, or on the way out delete one not worth keeping.

        A session the store has never seen has nothing to delete, so a closing write
        that would begin one writes nothing.
        """
        if session is None:
            return None
        if closing and not session.is_worth_keeping(self.minimum_duration):
            if session.id.value != 0:
                await self.session_repository.delete(session.id, session.user_id)
            return None
        stored = await self._save_if_still_there(session)
        if stored is None:
            return None
        if reached is not None:
            await self.session_repository.record_locator(stored.id, reached.locator, source_hash)
        return stored.id

    async def _save_if_still_there(self, session: ReadingSession) -> ReadingSession | None:
        """Save the session, or ``None`` if another tab's closing write deleted it meanwhile.

        The id comes back from the save rather than being written onto what was passed
        in, so an insert saved twice would be two rows.
        """
        try:
            return await self.session_repository.save(session)
        except ReadingSessionNotFoundError:
            return None

    async def _last_session(
        self, was_open: ReadingSessionId | None, user_id: UserId
    ) -> ReadingSession | None:
        """The session the stored position still points at, if it has not been deleted.

        ``None`` when the reader has never read this book here, or closed it last time.
        """
        if was_open is None:
            return None
        return await self.session_repository.find_by_id(was_open, user_id)

    def _has_gone_idle(self, session: ReadingSession, now: datetime) -> bool:
        """Whether nothing has been heard for long enough that this is a new sitting.

        Measured from the session's own end rather than from the stored position, so a
        session is judged on when it was really last extended.
        """
        return (now - as_aware(session.end_time)).total_seconds() > self.idle_seconds
