"""Derive a book's Readium Locators from an EPUB, one pass over each kind of row."""

import structlog

from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.protocols.reading_session_repository import (
    ReadingSessionRepositoryProtocol,
)
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.application.web_reader.publications import epub_content_hash
from src.application.web_reader.session_endpoints import endpoint_xpoints, paired_by_session
from src.domain.common.value_objects import BookId, HighlightId, UserId
from src.domain.common.value_objects.xpoint import XPointRange

logger = structlog.get_logger(__name__)

# The session repository pages rather than listing, and a whole book is what has
# to be rewritten; no reader has approached this many sessions for one book.
EVERY_SESSION = 10000


class BackfillBookLocatorsUseCase:
    """Place every stored highlight and reading session of one book against an EPUB."""

    def __init__(
        self,
        highlight_repository: HighlightRepositoryProtocol,
        session_repository: ReadingSessionRepositoryProtocol,
        position_anchor_service: PositionAnchorServiceProtocol,
    ) -> None:
        self.highlight_repository = highlight_repository
        self.session_repository = session_repository
        self._position_anchor_service = position_anchor_service

    async def backfill_book_locators(
        self, book_id: BookId, user_id: UserId, epub_content: bytes
    ) -> None:
        """Derive and store a Locator for each of this book's xpointed rows.

        Two parses rather than one: ranges and carets are separate port methods,
        and each amortises its parse over a whole kind (ADR-0004, *Amendment 6*).
        """
        source_hash = epub_content_hash(epub_content)
        await self._place_highlights(book_id, user_id, epub_content, source_hash)
        await self._place_sessions(book_id, user_id, epub_content, source_hash)

    async def _place_highlights(
        self, book_id: BookId, user_id: UserId, epub_content: bytes, source_hash: str
    ) -> None:
        highlights = await self.highlight_repository.find_by_book_id(book_id, user_id)
        ranges: dict[HighlightId, XPointRange] = {
            highlight.id: highlight.xpoints
            for highlight in highlights
            if highlight.xpoints is not None
        }
        if not ranges:
            return

        try:
            locators = await self._position_anchor_service.locators_for_xpoint_ranges(
                epub_content, ranges
            )
            await self.highlight_repository.bulk_update_locators(locators, source_hash)
        except Exception:
            logger.exception(
                "highlight_locator_backfill_failed", book_id=book_id.value, count=len(ranges)
            )

    async def _place_sessions(
        self, book_id: BookId, user_id: UserId, epub_content: bytes, source_hash: str
    ) -> None:
        sessions = await self.session_repository.find_by_book_id(
            book_id, user_id, limit=EVERY_SESSION, offset=0
        )
        points = endpoint_xpoints(sessions)
        if not points:
            return

        try:
            locators = await self._position_anchor_service.locators_for_xpoints(
                epub_content, points
            )
            await self.session_repository.bulk_update_locators(
                paired_by_session(points, locators), source_hash
            )
        except Exception:
            logger.exception(
                "reading_session_locator_backfill_failed",
                book_id=book_id.value,
                count=len(points) // 2,
            )
