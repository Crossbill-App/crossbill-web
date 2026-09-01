"""Pydantic schemas for the library-wide reading-activity API response."""

from datetime import date as calendar_date
from typing import Literal

from pydantic import BaseModel, Field

from src.infrastructure.reading.schemas.book_statistics_schemas import BookActivityDay


class ActivityBook(BaseModel):
    """A book the grid names, as the client needs it: a label and a link."""

    id: int = Field(..., description="ID of the book")
    title: str = Field(..., description="Title of the book")


class LibraryActivityDay(BookActivityDay):
    """One coloured square, and which books the reader spent it on."""

    book_ids: list[int] = Field(
        ...,
        description=(
            "Books read that day, in the order the reader opened them. A book that got "
            "through nothing that day is listed all the same"
        ),
    )


class LibraryActivity(BaseModel):
    """Every book's reading laid out day by day, for the activity grid.

    Sparse twice over: ``days`` carries only the days worth drawing, and each
    title is sent once in ``books`` for the days to reference by id.
    """

    unit: Literal["pages", "minutes"] = Field(
        ...,
        description=(
            "What each day's value counts. Pages as long as any session on the grid "
            "recorded them, minutes only when none did"
        ),
    )
    range_start: calendar_date = Field(..., description="First day of the window the grid spans")
    range_end: calendar_date = Field(..., description="Last day of the window the grid spans")
    days: list[LibraryActivityDay] = Field(..., description="Days with reading, oldest first")
    books: list[ActivityBook] = Field(
        ..., description="Every book the days name, alphabetically by title"
    )


class LibraryStats(BaseModel):
    """The year on the grid, said in numbers rather than squares.

    Counted over the same window as ``LibraryActivity``, but from the sessions:
    a day that got through no pages is a day read with no square to show for it.
    """

    last_read: calendar_date = Field(..., description="Most recent day with reading on the grid")
    seconds_today: int = Field(
        ..., description="Seconds read today, zero on a day nothing has been opened yet"
    )
    total_seconds: int = Field(..., description="Seconds read over the whole window")
    streak_days: int = Field(
        ...,
        description=(
            "Days read in a row, counting back from today; a today with no reading yet "
            "does not end a streak"
        ),
    )
    days_read: int = Field(..., description="Days in the window with reading on them")
    books_read: int = Field(..., description="Books the window's reading covered")


class LibraryReadingActivityResponse(BaseModel):
    """Schema for what every book of a reader's adds up to, day by day."""

    activity: LibraryActivity | None = Field(
        None,
        description=("The reader's daily activity, or null when there is no day worth colouring"),
    )
    stats: LibraryStats | None = Field(
        None,
        description=("What that activity adds up to, or null whenever there is no activity"),
    )
