"""Pydantic schemas for the ereader highlight-pull API."""

from datetime import datetime as dt
from typing import Final

from pydantic import BaseModel, field_serializer

# KOReader's own timestamp format. The plugin writes what we send here straight
# into a device annotation, so this response keeps the device's shape while the
# web API serves the same instants as ISO.
KOREADER_DATETIME_FORMAT: Final = "%Y-%m-%d %H:%M:%S"


class EreaderHighlightItem(BaseModel):
    """A single highlight as the device receives it back.

    ``note`` is the note written on the e-reader, not a Crossbill note.
    ``datetime_updated`` is when it was last edited on a device, null until it
    has been. ``placeable`` tells the device whether the highlight can be
    positioned in the book, which needs both xpoints.
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

    @field_serializer("datetime")
    def _created_as_koreader_datetime(self, value: dt) -> str:
        """Render the creation time the way KOReader writes it."""
        return value.strftime(KOREADER_DATETIME_FORMAT)

    @field_serializer("datetime_updated")
    def _edited_as_koreader_datetime(self, value: dt | None) -> str | None:
        """Render the last device edit the way KOReader writes it, if there is one."""
        return value.strftime(KOREADER_DATETIME_FORMAT) if value is not None else None
