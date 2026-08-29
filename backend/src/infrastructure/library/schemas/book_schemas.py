"""Pydantic schemas for Book API request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.library.entities.book import MAX_DESCRIPTION_LENGTH
from src.infrastructure.common.schemas.position_schemas import PositionResponse
from src.infrastructure.reading.schemas.highlight_schemas import ReadingStageLiteral


class BookReadingStageUpdateRequest(BaseModel):
    """Schema for updating a book's manual reading stage."""

    reading_stage: ReadingStageLiteral | None = Field(
        None, description="Reading stage, or null to clear it"
    )


class BookUpdateRequest(BaseModel):
    """Partial update of a book's own fields.

    A field the client omits is left untouched; a field sent as null is
    cleared. The router relies on `model_fields_set` to tell the two apart,
    so never give a field a non-None default.
    """

    # This schema's semantics are defined entirely by which keys are present
    # (see `model_fields_set` above), so an unrecognised key — e.g. a typo'd
    # field name, or a field not yet supported by this endpoint — must fail
    # loudly rather than parse to an empty `model_fields_set` and silently
    # no-op with a 204. Local tightening: no other schema in
    # `src/infrastructure` sets `extra="forbid"`.
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Book blurb in Markdown, or null to clear it",
    )


class BookBase(BaseModel):
    """Base schema for Book."""

    title: str = Field(..., min_length=1, max_length=500, description="Book title")
    author: str | None = Field(None, max_length=500, description="Book author")
    isbn: str | None = Field(None, max_length=20, description="Book ISBN")
    description: str | None = Field(None, description="Book description from ebook metadata")
    language: str | None = Field(
        None, max_length=10, description="Language code from ebook metadata"
    )
    page_count: int | None = Field(None, ge=1, description="Total page count from ebook metadata")


class BookCreate(BookBase):
    """Schema for creating a Book."""

    client_book_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Client-provided stable book identifier for deduplication",
    )


class Book(BookBase):
    """Schema for Book response."""

    id: int
    client_book_id: str | None = None
    created_at: datetime
    updated_at: datetime
    last_viewed: datetime | None = None

    model_config = {"from_attributes": True}


class BookWithHighlightCount(BaseModel):
    """Schema for Book with highlight, flashcard and note counts."""

    id: int
    client_book_id: str | None = None
    title: str
    author: str | None
    isbn: str | None
    cover_file: str | None = Field(None, description="Cover image filename (UUID.jpg) or null")
    cover_blurhash: str | None = Field(None, description="Blurhash string for cover placeholder")
    description: str | None = None
    language: str | None = None
    page_count: int | None = None
    highlight_count: int = Field(..., ge=0, description="Number of highlights for this book")
    flashcard_count: int = Field(0, ge=0, description="Number of flashcards for this book")
    note_count: int = Field(0, ge=0, description="Number of notes for this book, gists aside")
    reading_stage: ReadingStageLiteral | None = Field(
        None, description="Where the reader is with this book, or null if unset"
    )
    end_position: PositionResponse | None = Field(
        None, description="End position of the book (total document length)"
    )
    created_at: datetime
    updated_at: datetime
    last_viewed: datetime | None = None
    last_synced: datetime | None = Field(
        None, description="When a device last successfully sent data for this book"
    )

    model_config = {"from_attributes": True}


class EreaderBookMetadata(BaseModel):
    """Schema for ereader book metadata response.

    This lightweight response is used by KOReader to get basic book information
    for deciding whether to upload cover images, epub files, etc.
    """

    book_id: int = Field(..., description="Internal book ID")
    bookname: str = Field(..., description="Book title")
    author: str | None = Field(None, description="Book author")
    cover_file: str | None = Field(None, description="Cover image filename (UUID.jpg) or null")
    cover_blurhash: str | None = Field(None, description="Blurhash string for cover placeholder")
    has_ebook: bool = Field(..., description="Whether the book has an ebook file")
