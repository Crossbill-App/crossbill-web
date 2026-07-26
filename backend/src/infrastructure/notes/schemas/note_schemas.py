"""Pydantic schemas for Note API request/response validation."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from src.infrastructure.learning.schemas import Flashcard

NoteKindLiteral = Literal["character", "term", "concept", "gist", "reflection", "other"]

NoteTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class NoteLinkedChapter(BaseModel):
    """Lightweight summary of a chapter linked to a note."""

    id: int
    name: str


class NoteLinkedHighlight(BaseModel):
    """Lightweight summary of a highlight linked to a note."""

    id: int
    text: str


class NoteLinkedTag(BaseModel):
    """Lightweight summary of a tag linked to a note."""

    id: int
    name: str


class Note(BaseModel):
    """Schema for Note response."""

    id: int
    user_id: int
    title: str
    body: str
    kind: str | None
    book_ids: list[int]
    chapter_ids: list[int]
    highlight_ids: list[int]
    tag_ids: list[int]
    created_at: datetime
    updated_at: datetime


class NoteWithLinks(Note):
    """Note response with linked entity summaries."""

    chapters: list[NoteLinkedChapter] = Field(default_factory=list)
    highlights: list[NoteLinkedHighlight] = Field(default_factory=list)
    tags: list[NoteLinkedTag] = Field(default_factory=list)
    flashcards: list[Flashcard] = Field(default_factory=list)


class NoteCreateRequest(BaseModel):
    """Schema for creating a note."""

    title: NoteTitle = Field(..., description="Note title")
    body: str = Field("", description="Markdown body")
    kind: NoteKindLiteral | None = Field(None, description="Optional note kind")
    book_id: int = Field(..., description="Book this note is created in")
    chapter_ids: list[int] = Field(default_factory=list)
    highlight_ids: list[int] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)


class NoteCreateResponse(BaseModel):
    """Schema for note creation response."""

    success: bool = Field(..., description="Whether the creation was successful")
    message: str = Field(..., description="Response message")
    note: Note = Field(..., description="Created note")


class NoteUpdateRequest(BaseModel):
    """Schema for updating a note (full replace of fields and links)."""

    title: NoteTitle = Field(..., description="Note title")
    body: str = Field("", description="Markdown body")
    kind: NoteKindLiteral | None = Field(None, description="Optional note kind")
    chapter_ids: list[int] = Field(default_factory=list)
    highlight_ids: list[int] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)


class NoteUpdateResponse(BaseModel):
    """Schema for note update response."""

    success: bool = Field(..., description="Whether the update was successful")
    message: str = Field(..., description="Response message")
    note: Note = Field(..., description="Updated note")
