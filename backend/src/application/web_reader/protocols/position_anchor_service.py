"""Port for converting between the canonical xpointer and the Readium Locator."""

from collections.abc import Mapping
from typing import Protocol

from src.application.web_reader.anchors import AnchorMatch, Locator
from src.domain.common.value_objects.xpoint import XPoint, XPointRange


class PositionAnchorServiceProtocol(Protocol):
    """Derives web-reader anchors from stored positions, and reads them back.

    Three capabilities, per ADR-0004:

    1. **xpointer -> Locator** (:meth:`locator_for_xpoint`,
       :meth:`locator_for_xpoint_range`). Exact: the quote is read out of the
       EPUB. This is the read path the web reader renders highlights through.
    2. **Locator -> xpointer** (:meth:`xpoint_range_for_locator`). A text search,
       so it grades itself with an :class:`~src.application.web_reader.anchors.
       AnchorConfidence`. This is the write path: a selection made in the browser
       becomes an ``XPointRange`` before anything is stored.
    3. **Verification** (:meth:`verify_locator`). No conversion is trusted
       because it returned; the text a derived anchor covers is compared against
       the highlight text that was stored with the xpointer.

    Implementations parse the EPUB once per ``ebook_file`` and cache the result,
    so converting a whole book's highlights costs one parse. Nothing is persisted
    -- every Locator is computed on demand.
    """

    async def locator_for_xpoint(self, ebook_file: str, xpoint: XPoint) -> Locator:
        """Derive a Locator for a single position, e.g. a reading-progress point.

        The Locator carries an empty ``text.highlight`` with context meeting at
        the position, which is how a caret rather than a selection is expressed.

        Raises:
            AnchorResolutionError: If the EPUB is unavailable or the position
                does not resolve against it.
        """
        ...

    async def locator_for_xpoint_range(self, ebook_file: str, xpoints: XPointRange) -> Locator:
        """Derive a Locator for a highlight's range.

        Raises:
            AnchorResolutionError: If the EPUB is unavailable or either end does
                not resolve against it.
        """
        ...

    async def locators_for_xpoint_ranges(
        self, ebook_file: str, ranges: Mapping[int, XPointRange]
    ) -> dict[int, Locator | None]:
        """Derive Locators for many ranges of one book against a single parse.

        The whole-book conversion path. Callers hand in ranges keyed by whatever
        identifies them -- a highlight id -- and get the same keys back, mapped
        to a Locator or to ``None`` where that one range does not resolve. One
        bad xpointer is one missing view, not a failed request, so a per-range
        failure is a ``None`` rather than an exception (ADR-0004 §2).

        Implementations parse once and convert the whole mapping without
        returning to the event loop in between, which is what makes this
        different from a caller's own loop over
        :meth:`locator_for_xpoint_range`.

        Raises:
            AnchorResolutionError: If the *book* cannot be read at all -- no
                EPUB stored, or one that does not parse. That is a failure of
                every range at once and the caller degrades all of them.
        """
        ...

    async def xpoint_range_for_locator(self, ebook_file: str, locator: Locator) -> AnchorMatch:
        """Resolve a Locator back to the canonical ``XPointRange``, with a grade.

        Callers must check ``AnchorMatch.confidence`` against a floor before
        storing the result; a weak match is a bad position, not an error.

        Raises:
            AnchorResolutionError: If the EPUB is unavailable, the Locator names
                no resource in it, or its quote is nowhere to be found.
        """
        ...

    def verify_locator(self, locator: Locator, expected_text: str) -> bool:
        """Report whether a derived Locator covers the text that was stored.

        Comparison is whitespace- and soft-hyphen-tolerant, because crengine
        keeps soft hyphens in its DOM text and strips them from the highlight
        text it exports. ``False`` means the anchor is untrustworthy -- typically
        the EPUB file has been replaced with a differently typeset edition -- and
        the caller should show "cannot locate this" rather than a confident jump
        to the wrong paragraph.
        """
        ...
