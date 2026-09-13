"""Port between the canonical stored xpointers and the web reader's Locators."""

from collections.abc import Hashable, Mapping
from typing import Protocol

from src.application.web_reader.anchors import AnchorMatch, Locator
from src.domain.common.value_objects.xpoint import XPoint, XPointRange


class PositionAnchorServiceProtocol(Protocol):
    """Converts a book's positions between stored xpointers and Readium Locators.

    Deriving Locators, every caller is an ingest loop over one book's rows and
    already holds the EPUB bytes, so the unit of work is a mapping converted
    against a single parse (ADR-0004, *Amendment 6*). A caller with one position
    passes a one-entry mapping.

    Keys are the caller's own and come back unchanged: a highlight id, or a
    ``(session_id, "start")`` pair so both ends of a session cost one parse.
    """

    async def locators_for_xpoint_ranges[K: Hashable](
        self, epub_content: bytes, ranges: Mapping[K, XPointRange]
    ) -> dict[K, Locator | None]:
        """Derive a Locator per range, or ``None`` where that range does not resolve.

        One unresolvable xpointer is one missing view, not a failed batch
        (ADR-0004 §2) -- a document of the book that cannot be read fails only
        the ranges pointing into it.

        Raises:
            AnchorResolutionError: If the archive itself cannot be read -- every
                range failing at once, which the caller degrades as a whole.
        """
        ...

    async def locators_for_xpoints[K: Hashable](
        self, epub_content: bytes, points: Mapping[K, XPoint]
    ) -> dict[K, Locator | None]:
        """Derive a caret Locator per position, or ``None`` where one does not resolve.

        A caret carries an empty ``text.highlight`` with the context meeting at
        the position, which is how a reading-session endpoint differs from a
        selection.

        Raises:
            AnchorResolutionError: If the archive itself cannot be read.
        """
        ...

    async def xpoint_range_for_locator(self, epub_content: bytes, locator: Locator) -> AnchorMatch:
        """Resolve one browser-made Locator back to the canonical coordinates.

        One at a time, not a batch: the write path converts the single selection
        a reader just made. The match is **graded, not filtered** -- a caller
        that stores the range must check ``confidence`` against a floor of its
        own first (ADR-0004 §5).

        Raises:
            AnchorNotFoundError: If a readable EPUB does not hold the place the
                Locator names -- no such resource, the quote nowhere to be
                found, or no text to search by at all. That last is the ordinary
                shape of a reading position, and synthesising a quote for one is
                #830's.
            AnchorResolutionError: If the EPUB itself cannot be read.
        """
        ...

    def verify_locator(self, locator: Locator, expected_text: str) -> bool:
        """Report whether a Locator's quote is the text that was stored.

        Synchronous and EPUB-free: a Locator's ``text.highlight`` was read out of
        the document when the Locator was built, so this is a comparison rather
        than a second pass. Whitespace and soft hyphens do not count against a
        match -- crengine keeps soft hyphens in its DOM text and strips them from
        the highlight text it exports, so the two differ cosmetically on anything
        hyphenated.
        """
        ...
