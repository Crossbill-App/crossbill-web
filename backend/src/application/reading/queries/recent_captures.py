"""Read model for the landing page's row of the reader's latest captures.

Highlights and notes on one timeline. The ``notes`` module's rows join in here
rather than in either aggregate, because neither domain module may reach into
the other; see ``docs/adr/0001-read-models-and-query-services.md``.

Every timestamp on these DTOs is a local wall clock with no offset: a
highlight's is the e-reader's own, a note's has been converted into the
reader's zone. They are comparable to each other and to nothing else.
"""

from dataclasses import dataclass
from datetime import date, tzinfo
from datetime import datetime as dt
from enum import StrEnum
from typing import Protocol

from src.application.common.queries.highlight_row import HighlightLabelView
from src.domain.common.value_objects.ids import UserId


class CaptureKind(StrEnum):
    """What one row of the feed is."""

    HIGHLIGHT = "highlight"
    NOTE = "note"


@dataclass(frozen=True)
class RecentCaptureView:
    """One highlight or note, with everything the feed prints beside it.

    A highlight fills ``text``, ``page`` and ``label``; a note fills ``title``,
    ``note_kind`` and puts its body in ``text``. ``chapter_name`` is a
    highlight's chapter, and null for a note.
    """

    kind: CaptureKind
    id: int
    book_id: int
    book_title: str
    chapter_name: str | None
    title: str | None
    text: str
    note_kind: str | None
    page: int | None
    label: HighlightLabelView | None
    captured_at: dt
    day: date
    more_in_book: int
    """Captures of this book, day and kind that the feed does not show.

    Non-zero only on the last capture of that book, day and kind, so a renderer
    prints "+N more" once without counting anything itself.
    """


class RecentCapturesQueryProtocol(Protocol):
    """Port for reading the newest highlights and notes across a reader's library."""

    async def get_recent_captures(
        self, user_id: UserId, zone: tzinfo, limit: int
    ) -> tuple[RecentCaptureView, ...]:
        """Return the reader's newest captures, newest first.

        ``zone`` decides which calendar day a note falls on, and is passed in
        rather than read from the clock so the day line is drawn at the edge.
        """
        ...
