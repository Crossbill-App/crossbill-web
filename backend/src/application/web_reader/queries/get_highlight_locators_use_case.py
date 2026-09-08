"""Derive verified Readium locators for a book's highlights (M3.1, #745).

This is the cross-module composition ADR-0004 §6 leaves room for: the highlights
are ``reading``'s and stay there, and what the web reader adds is the derivation
and the verification around it. The dependency runs one way -- this use case
reads ``reading``'s canonical positions through a port of its own, and nothing
in ``reading`` learns that locators exist.
"""

import logging

from src.application.web_reader.anchors import AnchorResolutionError, Locator
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.application.web_reader.queries.highlight_locators import (
    BookHighlightAnchors,
    DerivedHighlightLocator,
    HighlightAnchor,
    HighlightAnchorQueryProtocol,
    LocatorUnavailable,
)
from src.domain.common.value_objects.ids import BookId, HighlightId, UserId
from src.domain.common.value_objects.xpoint import XPointRange
from src.domain.reading.exceptions import BookNotFoundError, HighlightNotFoundError

logger = logging.getLogger(__name__)


class GetHighlightLocatorsUseCase:
    """Places a book's highlights in its EPUB, one parse per book.

    Every answer is per-highlight: a book whose EPUB has been replaced comes
    back as a full set of highlights that each say they cannot be placed, not as
    an error. That is what makes the derived layer safe to be lossy (ADR-0004
    §5) -- the canonical xpointers are untouched either way, and the reader is
    told which highlights it cannot draw rather than being handed a wrong place
    or nothing at all.
    """

    def __init__(
        self,
        highlight_anchor_query: HighlightAnchorQueryProtocol,
        position_anchor_service: PositionAnchorServiceProtocol,
    ) -> None:
        """Initialize with the canonical-position port and the anchor port."""
        self.highlight_anchor_query = highlight_anchor_query
        self.position_anchor_service = position_anchor_service

    async def for_book(
        self, book_id: BookId, user_id: UserId
    ) -> dict[int, DerivedHighlightLocator]:
        """Derive locators for every live highlight of a book, keyed by highlight id.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        anchors = await self.highlight_anchor_query.anchors_for_book(book_id, user_id)
        if anchors is None:
            raise BookNotFoundError(book_id.value)
        return await self._derive(anchors)

    async def for_highlight(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> DerivedHighlightLocator:
        """Derive the locator for one highlight.

        Raises:
            HighlightNotFoundError: If the user has no such live highlight.
        """
        anchors = await self.highlight_anchor_query.anchor_for_highlight(highlight_id, user_id)
        if anchors is None:
            raise HighlightNotFoundError(highlight_id.value)
        derived = await self._derive(anchors)
        return derived[highlight_id.value]

    async def _derive(self, anchors: BookHighlightAnchors) -> dict[int, DerivedHighlightLocator]:
        """Convert and verify a book's highlights against one parsed publication."""
        placeable = {
            anchor.highlight_id: anchor.xpoints
            for anchor in anchors.highlights
            if anchor.xpoints is not None
        }
        converted = await self._converted(anchors.ebook_file, placeable)
        return {
            anchor.highlight_id: self._answer(anchor, anchors.ebook_file, converted)
            for anchor in anchors.highlights
        }

    async def _converted(
        self, ebook_file: str | None, placeable: dict[int, XPointRange]
    ) -> dict[int, Locator | None]:
        """The conversions the anchor port could make, empty if the book cannot be read.

        A book-wide failure -- no EPUB stored, or one that will not parse -- is
        caught here rather than raised, because it degrades every highlight
        equally and each of them reports it for itself.
        """
        if ebook_file is None or not placeable:
            return {}
        try:
            return await self.position_anchor_service.locators_for_xpoint_ranges(
                ebook_file, placeable
            )
        except AnchorResolutionError as exc:
            logger.info("unreadable_publication_for_highlights", extra={"reason": str(exc)})
            return {}

    def _answer(
        self,
        anchor: HighlightAnchor,
        ebook_file: str | None,
        converted: dict[int, Locator | None],
    ) -> DerivedHighlightLocator:
        """Grade one highlight's conversion, verifying it before trusting it."""
        if ebook_file is None:
            return _unavailable(anchor, LocatorUnavailable.NO_EBOOK)
        if anchor.xpoints is None:
            return _unavailable(anchor, LocatorUnavailable.NOT_PLACEABLE)

        locator = converted.get(anchor.highlight_id)
        if locator is None:
            return _unavailable(anchor, LocatorUnavailable.UNRESOLVED)
        if not self.position_anchor_service.verify_locator(locator, anchor.text):
            return _unavailable(anchor, LocatorUnavailable.TEXT_MISMATCH)
        return DerivedHighlightLocator(highlight_id=anchor.highlight_id, locator=locator)


def _unavailable(anchor: HighlightAnchor, reason: LocatorUnavailable) -> DerivedHighlightLocator:
    """The answer for a highlight that cannot be placed, with the reason why."""
    return DerivedHighlightLocator(highlight_id=anchor.highlight_id, unavailable=reason)
