"""Pydantic schemas for the book reading-statistics API response."""

from datetime import date as calendar_date
from datetime import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class BookActivityDay(BaseModel):
    """One coloured square of the reading-activity grid."""

    date: calendar_date = Field(..., description="The calendar day, in the requested timezone")
    value: int = Field(..., description="Pages read, or minutes read, per the grid's unit")
    level: int = Field(..., description="Shade of the square, 1-4; days with nothing are omitted")


class BookActivity(BaseModel):
    """A book's reading laid out day by day, for the activity grid.

    Sparse on purpose: ``days`` carries only the days with something to show,
    oldest first, and the window the grid spans is ``range_start`` to
    ``range_end`` regardless. The client fills the gaps.
    """

    unit: Literal["pages", "minutes"] = Field(
        ...,
        description=(
            "What each day's value counts. Pages when every session of the book "
            "recorded them, minutes otherwise"
        ),
    )
    range_start: calendar_date = Field(..., description="First day of the window the grid spans")
    range_end: calendar_date = Field(..., description="Last day of the window the grid spans")
    days: list[BookActivityDay] = Field(..., description="Days with reading, oldest first")


class BookReadingStatistics(BaseModel):
    """Schema for what a book's reading sessions add up to.

    A field is null when there is nothing to compute it from, rather than zero:
    a book nobody has opened has no average session, and one with no recorded
    position is not at 0% -- it is unknown.
    """

    session_count: int = Field(..., description="Reading sessions recorded for the book")
    total_reading_seconds: int = Field(..., description="Time spent reading the book, in seconds")
    average_session_seconds: int | None = Field(
        None, description="Mean length of a session, in seconds"
    )
    first_session_start: dt | None = Field(None, description="When the first session began")
    last_session_end: dt | None = Field(None, description="When the last session ended")
    span_days: int | None = Field(
        None,
        description=(
            "Calendar days from the first session to the last, counted inclusively "
            "in the requested timezone"
        ),
    )
    progress_percent: int | None = Field(
        None, description="How far through the book the reader has got, 0-100"
    )
    activity: BookActivity | None = Field(
        None,
        description=(
            "Daily reading activity for the grid, or null when there is no day worth colouring"
        ),
    )
