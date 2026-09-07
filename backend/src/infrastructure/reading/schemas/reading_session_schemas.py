"""Pydantic schemas for Reading Session API request/response validation."""

from datetime import UTC
from datetime import datetime as dt
from typing import TYPE_CHECKING, Annotated, Self

from pydantic import AfterValidator, BaseModel, Field, model_validator

from src.domain.common.devices import WEB_READER_DEVICE_ID

if TYPE_CHECKING:
    # Import at runtime is handled below to avoid circular imports
    pass


def _instant(value: dt) -> dt:
    """Insist a synced session says *when* it was, and normalise it to UTC.

    A reading session is the one thing the plugin sends that is compared
    against a clock other than its own: the web reader's resume weighs a
    session's ``end_time`` against the moment a browser recorded a position, and
    picks the later (ADR-0004, Amendment 4). A timestamp with no offset cannot
    be weighed. Stamping one UTC would put a device in Helsinki three hours into
    its own future and let a session it finished this morning beat a page the
    reader turned in a browser this afternoon.

    So a session's moments must carry an offset. This is *not* the rule the
    highlight path follows, and the difference is not an oversight in either:
    KOReader's annotations carry the device's own wall clock with no offset to
    parse (``highlight_schemas._drop_offset``), while the plugin builds session
    times from Unix epochs through ``os.date("!%Y-%m-%dT%H:%M:%SZ")`` -- the
    ``!`` being UTC -- and has done since the commit that first synced a
    session. Requiring here what the plugin has always sent therefore refuses
    nothing any released plugin produces, which is why it needs no bump of the
    ``koreader-plugin`` minimum.

    What it does close is a silent one. Bare ``datetime`` accepted a naive value
    and handed it to a ``timestamptz`` column, where PostgreSQL reads it in
    whatever the connection's ``TimeZone`` happens to be -- so the same request
    meant different instants on different deployments, and nothing anywhere
    said so.
    """
    if value.tzinfo is None:
        raise ValueError(
            "must carry a UTC offset -- a session with no offset names no instant "
            "(KOReader sends '2024-01-15T10:00:00Z')"
        )
    return value.astimezone(UTC)


SessionInstant = Annotated[dt, AfterValidator(_instant)]


def _not_reserved(value: str | None) -> str | None:
    """Refuse the device id Crossbill keeps for reading done in the browser.

    A synced session wearing this name would be taken for one the web reader
    wrote and left out of the resume's search for where another device left off
    -- so it would silently never be resumed from, which is a wrong answer
    rather than a missing one. No e-reader is called this: the name was minted
    by Crossbill in M2.3 for its own sessions, so refusing it takes nothing away
    from any client that exists and needs no bump of the plugin minimum.

    422 rather than a quiet rename: a caller sending this is either confused
    about which client it is or claiming to be one it is not, and both are worth
    being told about.
    """
    if value == WEB_READER_DEVICE_ID:
        raise ValueError(f"'{WEB_READER_DEVICE_ID}' is reserved for reading done in the browser")
    return value


class ReadingSessionBase(BaseModel):
    """Base schema for ReadingSession."""

    book_id: int
    device_id: str | None
    content_hash: str
    start_time: dt = Field(..., description="Session start timestamp")
    end_time: dt = Field(..., description="Session end timestamp")
    start_page: int | None = Field(None, ge=0, description="Start page number")
    end_page: int | None = Field(None, ge=0, description="End page number")


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


class ReadingSessionSyncItem(BaseModel):
    """Schema for a single reading session in the sync request."""

    start_time: SessionInstant = Field(
        ..., description="Session start, with a UTC offset (KOReader sends '...Z')"
    )
    end_time: SessionInstant = Field(
        ..., description="Session end, with a UTC offset (KOReader sends '...Z')"
    )
    start_xpoint: str | None = Field(None, description="Start position (xpoint string)")
    end_xpoint: str | None = Field(None, description="End position (xpoint string)")
    start_page: int | None = Field(None, ge=0, description="Start page number")
    end_page: int | None = Field(None, ge=0, description="End page number")
    device_id: Annotated[str | None, AfterValidator(_not_reserved)] = Field(
        None,
        max_length=100,
        description=(
            f"Device identifier. '{WEB_READER_DEVICE_ID}' is reserved for reading "
            "done in the browser and is refused here."
        ),
    )

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


class ReadingSessionSyncRequest(BaseModel):
    """Schema for syncing reading sessions from KOReader."""

    client_book_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Client-provided stable book identifier for deduplication",
    )
    sessions: list[ReadingSessionSyncItem] = Field(
        ..., min_length=1, description="List of reading sessions for this book"
    )


class ReadingSessionSyncResponse(BaseModel):
    """Schema for reading session sync response.

    Note: If any session is invalid,
    the entire request fails with 422 and this response is never returned.
    """

    success: bool = Field(..., description="Whether the sync was successful (always True)")
    message: str = Field(..., description="Response message")
    book_id: int = Field(..., description="ID of the book for these sessions")
    created_count: int = Field(0, description="Number of sessions created")
    skipped_duplicate_count: int = Field(0, description="Sessions skipped because already synced")
