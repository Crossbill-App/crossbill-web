"""Derive verified Readium locators for a book's highlights (M3.1, #745).

This is the cross-module composition ADR-0004 §6 leaves room for: the highlights
are ``reading``'s and stay there, and what the web reader adds is the derivation
and the verification around it. The dependency runs one way -- this use case
reads ``reading``'s canonical positions through a port of its own, and nothing
in ``reading`` learns that locators exist.
"""

from collections.abc import Collection
from functools import lru_cache

import structlog

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

logger = structlog.get_logger(__name__)

#: The failures worth a warning, and why the other three are not (M3.4, #748).
#:
#: These two are *conversions that went wrong* against an EPUB that read and
#: parsed: an xpointer that named nothing, or one that landed on the wrong
#: words. Those are the cases xpoint-cfi needs as corpus material, and each one
#: is a book and a highlight somebody can go and look at.
#:
#: ``NO_EBOOK`` is a missing file rather than a bad conversion, and it would log
#: once per highlight for every highlight in the book. ``NOT_PLACEABLE`` is a
#: highlight that never had a position to convert -- ordinary for anything typed
#: in by hand or synced by an older plugin. ``GONE`` is a delete landing between
#: two reads. None of the three says anything about the conversion.
_WORTH_REPORTING = frozenset({LocatorUnavailable.UNRESOLVED, LocatorUnavailable.TEXT_MISMATCH})


@lru_cache(maxsize=4096)
def _report_unconvertible(book_id: int, highlight_id: int, reason: LocatorUnavailable) -> None:
    """Log one bad conversion, once per process.

    The whole-book route is called every time a reader opens a book, so logging
    at derivation time would repeat the same line for the same broken highlight
    all day and bury the ones that are new. The cache is the once-ness: an
    ``lru_cache`` over a function that returns nothing calls the body the first
    time it sees a key and never again, and evicts the least recently seen when
    it is full -- which is the whole of the rate limiting this needs. A restart
    starts the log over, which is the right granularity for collecting corpus
    cases rather than for alerting.

    Keyed on the reason too, so a highlight that stops resolving and starts
    landing on the wrong words is reported again: that is a different fact about
    it.
    """
    logger.warning(
        "highlight_locator_unavailable",
        book_id=book_id,
        highlight_id=highlight_id,
        reason=reason.value,
    )


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
        self,
        book_id: BookId,
        user_id: UserId,
        highlight_ids: Collection[int] | None = None,
    ) -> dict[int, DerivedHighlightLocator]:
        """Derive locators for a book's live highlights, keyed by highlight id.

        ``highlight_ids`` restricts the work to the highlights the caller will
        render. That is not an optimisation to skip when convenient: conversion
        cost is per highlight (ADR-0004 §4), so a view showing three matches out
        of a heavily annotated book would otherwise pay for all of them.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        anchors = await self.highlight_anchor_query.anchors_for_book(
            book_id, user_id, highlight_ids
        )
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
        converted, unreadable = await self._converted(anchors.ebook_file, placeable)
        derived = {
            anchor.highlight_id: self._answer(anchor, unreadable, converted)
            for anchor in anchors.highlights
        }
        # After the answers rather than inside `_answer`, so that what is logged
        # is what the caller was actually told (M3.4, #748). The reader is not
        # shown a word of this: a book of broken conversions would be a book of
        # notices. It is written down so the conversions can be fixed.
        for answer in derived.values():
            reason = answer.unavailable
            if reason is not None and reason in _WORTH_REPORTING:
                _report_unconvertible(anchors.book_id, answer.highlight_id, reason)
        return derived

    async def _converted(
        self, ebook_file: str | None, placeable: dict[int, XPointRange]
    ) -> tuple[dict[int, Locator | None], LocatorUnavailable | None]:
        """The conversions the anchor port could make, and whether the book defeated it.

        A book-wide failure is caught here rather than raised, because it
        degrades every highlight equally and each of them reports it for itself.
        But it is carried back out as a *reason* rather than as an empty
        mapping: an empty mapping is indistinguishable from "every one of these
        xpointers failed", and answering a missing file with ``UNRESOLVED``
        would tell a reader their positions were lost when what is gone is the
        EPUB. The anchor port raises here only for the whole book -- a range it
        cannot convert comes back as a ``None`` value inside the mapping -- so
        catching it is unambiguous.
        """
        if ebook_file is None:
            return {}, LocatorUnavailable.NO_EBOOK
        if not placeable:
            return {}, None
        try:
            converted = await self.position_anchor_service.locators_for_xpoint_ranges(
                ebook_file, placeable
            )
        except AnchorResolutionError as exc:
            logger.info(
                "unreadable_publication_for_highlights",
                ebook_file=ebook_file,
                reason=str(exc),
            )
            return {}, LocatorUnavailable.NO_EBOOK
        return converted, None

    def _answer(
        self,
        anchor: HighlightAnchor,
        unreadable: LocatorUnavailable | None,
        converted: dict[int, Locator | None],
    ) -> DerivedHighlightLocator:
        """Grade one highlight's conversion, verifying it before trusting it."""
        if unreadable is not None:
            return _unavailable(anchor, unreadable)
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
