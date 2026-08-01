"""Pydantic schemas for Reading Session API request/response validation."""

from datetime import datetime as dt
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    # Import at runtime is handled below to avoid circular imports
    pass


class ReadingSessionBase(BaseModel):
    """Base schema for ReadingSession."""

    book_id: int
    device_id: str | None
    content_hash: str
    start_time: dt = Field(..., description="Session start timestamp")
    end_time: dt = Field(..., description="Session end timestamp")
    start_page: int | None = Field(None, ge=0, description="Start page number")
    end_page: int | None = Field(None, ge=0, description="End page number")
    content: str | None = Field(None, description="Extracted text content of the session")
    ai_summary: str | None = Field(None, description="AI generated summary of the read content")


# Import Highlight after ReadingSessionBase is defined to avoid circular import issues
from src.infrastructure.reading.schemas.highlight_schemas import Highlight  # noqa: E402


class ReadingSession(ReadingSessionBase):
    """Schema for ReadingSession response."""

    id: int
    created_at: dt
    highlights: list[Highlight] = Field(
        ..., description="Highlights that appear within this reading session"
    )

    model_config = {"from_attributes": True}


class ReadingSessionUploadSessionItem(BaseModel):
    """Schema for a single reading session in the upload request."""

    start_time: dt = Field(..., description="Session start timestamp")
    end_time: dt = Field(..., description="Session end timestamp")
    start_xpoint: str | None = Field(None, description="Start position (xpoint string)")
    end_xpoint: str | None = Field(None, description="End position (xpoint string)")
    start_page: int | None = Field(None, ge=0, description="Start page number")
    end_page: int | None = Field(None, ge=0, description="End page number")
    device_id: str | None = Field(None, max_length=100, description="Device identifier")

    @model_validator(mode="after")
    def check_position_fields(self) -> Self:
        """Validate that at least one position type is provided."""
        has_xpoint = self.start_xpoint is not None and self.end_xpoint is not None
        has_page = self.start_page is not None and self.end_page is not None

        if not has_xpoint and not has_page:
            raise ValueError(
                "You must define at least either (start_xpoint & end_xpoint) "
                "or (start_page & end_page)."
            )
        return self


class ReadingSessionUploadRequest(BaseModel):
    """Schema for uploading reading sessions from KOReader."""

    client_book_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Client-provided stable book identifier for deduplication",
    )
    sessions: list[ReadingSessionUploadSessionItem] = Field(
        ..., min_length=1, description="List of reading sessions for this book"
    )


class ReadingSessionUploadResponse(BaseModel):
    """Schema for reading session upload response.

    Note: If any session is invalid,
    the entire request fails with 422 and this response is never returned.
    """

    success: bool = Field(..., description="Whether the upload was successful (always True)")
    message: str = Field(..., description="Response message")
    book_id: int = Field(..., description="ID of the book for these sessions")
    created_count: int = Field(0, description="Number of sessions created")
    skipped_duplicate_count: int = Field(0, description="Sessions skipped because already uploaded")


class ReadingSessionAISummaryResponse(BaseModel):
    """Schema for AI summary response."""

    summary: str = Field(..., description="AI-generated summary of the reading session")
