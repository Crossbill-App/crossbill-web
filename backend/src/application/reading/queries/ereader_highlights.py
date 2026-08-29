"""Read model for the ereader's highlight list.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class EreaderHighlightView:
    """A single highlight, as the device receives it back.

    ``note`` is the note written on the e-reader (the highlight's
    ``koreader_note``), not a Crossbill note. ``datetime_updated`` is when the
    highlight was last edited on a device, which the device compares against
    its own copy. ``placeable`` says whether the device can position the
    highlight in the book: that needs both xpoints, and highlights uploaded
    from a device without them never gain them server-side.
    """

    id: int
    text: str
    start_xpoint: str | None
    end_xpoint: str | None
    datetime: dt
    datetime_updated: dt | None
    page: int | None
    chapter_number: int | None
    chapter_name: str | None
    device_color: str | None
    device_style: str | None
    note: str | None
    origin_device_id: str | None
    placeable: bool


class EreaderHighlightsQueryProtocol(Protocol):
    """Port for reading a book's highlights for the device."""

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[EreaderHighlightView, ...]:
        """Return the book's live highlights, oldest position first."""
        ...
