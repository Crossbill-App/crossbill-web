"""Port for deriving Readium Locators from the canonical stored xpointers."""

from collections.abc import Hashable, Mapping
from typing import Protocol

from src.application.web_reader.anchors import Locator
from src.domain.common.value_objects.xpoint import XPoint, XPointRange


class PositionAnchorServiceProtocol(Protocol):
    """Derives a book's Readium Locators from its stored xpointers, a batch at a time.

    Every caller is an ingest loop over one book's rows and already holds the
    EPUB bytes, so the unit of work is a mapping converted against a single
    parse (ADR-0004, *Amendment 6*). A caller with one position passes a
    one-entry mapping.

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
