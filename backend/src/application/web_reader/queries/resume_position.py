"""The read model behind "where should the web reader open this book?".

This is not the same question as "what did the web reader last store". A reader
who left off on their e-reader has no stored web position at all, and one who
read in the browser last week and on the e-reader yesterday has one that is out
of date. The view below is the answer to the question the browser actually asks
when a book opens, and it carries enough about *how* it was reached for the
reader to tell a restored position from a fallback to the beginning.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from src.application.web_reader.anchors import Locator
from src.domain.common.value_objects import XPoint
from src.domain.common.value_objects.position import Position


class ResumeSource(StrEnum):
    """Which reader the position being resumed from came from.

    Attributes:
        WEB: The row the browser itself wrote. It carries the locator verbatim,
            so the reader is put back exactly where it was.
        KOREADER: The end of a reading session synced from an e-reader. Only an
            xpointer was stored, so a locator has to be derived from the EPUB --
            which is the conversion that can fail.
    """

    WEB = "web"
    KOREADER = "koreader"


@dataclass(frozen=True)
class ResumePosition:
    """Where to open a book, and what that answer rests on.

    Three states, and the reader treats each differently:

    - **Nothing at all** (``source is None``): the book has never been read on
      any device. It opens at the beginning, silently, because that is not a
      failure.
    - **Resolved** (a locator): navigate there.
    - **Unresolved** (``source`` set, no locator): a position exists and could
      not be placed in the EPUB this server now holds -- the shape a replaced
      edition takes (ADR-0004 §5). The book opens at the beginning *and says so*,
      because the reader is entitled to know their place was lost rather than
      never recorded.

    The two locator fields are two different things rather than one field said
    twice. ``stored_locator`` is the JSON the navigator itself produced, kept
    byte for byte -- its hrefs are the ones the manifest published and every
    field a navigator understands is still on it, including the ones this
    codebase has no vocabulary for. ``derived_locator`` was computed here from
    an xpointer, so its hrefs are paths inside the EPUB container and something
    has to point them back at the URLs that serve them. Collapsing the two would
    mean parsing the stored one into a shape that drops what it does not know.

    Attributes:
        source: Which reader the position came from, or ``None`` if there is no
            position on any device.
        stored_locator: The web reader's own locator, verbatim.
        derived_locator: A locator computed from an e-reader's xpointer, in
            container coordinates.
        xpoint: The canonical position both readers agree on, whether or not a
            locator could be derived from it.
        position: Where that is in document order, if it could be placed.
        recorded_at: When the reader was there. The web position's own
            ``recorded_at``, or the moment an e-reader's session ended.
    """

    source: ResumeSource | None = None
    stored_locator: Mapping[str, Any] | None = None
    derived_locator: Locator | None = None
    xpoint: XPoint | None = None
    position: Position | None = None
    recorded_at: datetime | None = None

    @property
    def resolved(self) -> bool:
        """Whether there is a locator to navigate to."""
        return self.stored_locator is not None or self.derived_locator is not None

    @property
    def unresolved(self) -> bool:
        """Whether a position exists that could not be placed in this EPUB."""
        return self.source is not None and not self.resolved


NOWHERE = ResumePosition()
"""The answer for a book nobody has read anywhere: open at the beginning."""
