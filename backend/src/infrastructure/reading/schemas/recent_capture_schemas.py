"""Pydantic schemas for the reader's latest highlights and notes."""

from datetime import date as calendar_date
from datetime import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from src.infrastructure.reading.schemas.highlight_schemas import HighlightLabel


class RecentCapture(BaseModel):
    """One highlight or note in the feed of what the reader last captured."""

    kind: Literal["highlight", "note"] = Field(..., description="What this capture is")
    id: int = Field(..., description="ID of the highlight or the note")
    book_id: int = Field(..., description="Book the capture belongs to")
    book_title: str = Field(..., description="Title of that book")
    chapter_name: str | None = Field(
        None, description="Chapter the highlight sits in; null for a note"
    )
    title: str | None = Field(None, description="Title of the note; null for a highlight")
    text: str = Field(..., description="The highlighted passage, or the note's body")
    note_kind: str | None = Field(None, description="Kind of the note; null for a highlight")
    page: int | None = Field(None, description="Page the highlight was made on, where known")
    label: HighlightLabel | None = Field(
        None, description="The highlight's resolved label; null for a note"
    )
    captured_at: dt = Field(
        ...,
        description=(
            "When the capture was made, as a local wall clock with no offset: the "
            "e-reader's own for a highlight, the reader's zone for a note"
        ),
    )
    day: calendar_date = Field(..., description="Calendar day the capture is filed under")
    more_in_book: int = Field(
        ...,
        description=(
            "Captures of the same book, day and kind the feed does not show. Non-zero "
            "on the last capture of that book, day and kind, zero everywhere else"
        ),
    )
