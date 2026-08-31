"""Pydantic schemas for the book reading-statistics API response."""

from datetime import datetime as dt

from pydantic import BaseModel, Field


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
