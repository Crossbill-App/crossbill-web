"""Pydantic schemas for the ereader highlight-pull API."""

from pydantic import BaseModel


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
    datetime: str
    datetime_updated: str | None
    page: int | None
    chapter_number: int | None
    chapter_name: str | None
    device_color: str | None
    device_style: str | None
    note: str | None
    origin_device_id: str | None
    placeable: bool
