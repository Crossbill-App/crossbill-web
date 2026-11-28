"""Pydantic schemas for Flashcard API request/response validation."""

from datetime import datetime as dt
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

FlashcardStatusLiteral = Literal["active", "suspended"]
FlashcardOriginLiteral = Literal["manual", "generated"]
FlashcardRatingLiteral = Literal["again", "hard", "good", "easy"]


class Flashcard(BaseModel):
    """Schema for Flashcard response (without embedded highlight)."""

    id: int
    user_id: int
    book_id: int
    highlight_id: int | None
    chapter_id: int | None = None
    note_id: int | None = None

    question: str = Field(..., min_length=1, description="Question text for the flashcard")
    answer: str = Field(..., min_length=1, description="Answer text for the flashcard")
    status: FlashcardStatusLiteral = Field(
        ..., description="A suspended card is never due and takes no reviews"
    )
    origin: FlashcardOriginLiteral = Field(..., description="Written by the reader or generated")
    due: dt | None = Field(..., description="When the card is next due; null until first reviewed")
    last_review: dt | None = Field(..., description="When the card was last reviewed")

    model_config = {"from_attributes": True}


class ReviewFlashcard(Flashcard):
    """A flashcard with the book, chapter and source a review shows it with."""

    book_title: str
    chapter_name: str | None = Field(
        ..., description="The flashcard's chapter, else its highlight's"
    )
    highlight_text: str | None = Field(
        ..., description="Text of the highlight the flashcard came from"
    )
    note_title: str | None = Field(..., description="Title of the note the flashcard came from")


class RatingPreviews(BaseModel):
    """When the flashcard would next be due after each rating given now."""

    again: dt
    hard: dt
    good: dt
    easy: dt


class DueFlashcard(ReviewFlashcard):
    """A Due Flashcard with its rating previews."""

    previews: RatingPreviews


class FlashcardCreateRequest(BaseModel):
    """Schema for creating a new flashcard."""

    question: str = Field(..., min_length=1, description="Question text for the flashcard")
    answer: str = Field(..., min_length=1, description="Answer text for the flashcard")
    chapter_id: int | None = Field(None, description="Optional chapter ID to associate with")


class NoteFlashcardCreateRequest(BaseModel):
    """Schema for creating a new flashcard linked to a note."""

    question: str = Field(..., min_length=1, description="Question text for the flashcard")
    answer: str = Field(..., min_length=1, description="Answer text for the flashcard")
    book_id: int | None = Field(
        None,
        description=(
            "Book (must be linked to the note) to file the flashcard under; "
            "defaults to the note's first book"
        ),
    )


class FlashcardCreateResponse(BaseModel):
    """Schema for flashcard creation response."""

    success: bool = Field(..., description="Whether the creation was successful")
    message: str = Field(..., description="Response message")
    flashcard: Flashcard = Field(..., description="Created flashcard")


class FlashcardUpdateRequest(BaseModel):
    """Schema for updating a flashcard."""

    question: str | None = Field(None, min_length=1, description="New question text")
    answer: str | None = Field(None, min_length=1, description="New answer text")


class FlashcardUpdateResponse(BaseModel):
    """Schema for flashcard update response."""

    success: bool = Field(..., description="Whether the update was successful")
    message: str = Field(..., description="Response message")
    flashcard: Flashcard = Field(..., description="Updated flashcard")


class FlashcardSuggestionItem(BaseModel):
    """Schema for a single AI-generated flashcard suggestion."""

    question: str = Field(..., description="Suggested question for flashcard")
    answer: str = Field(..., description="Suggested answer for flashcard")


class FlashcardReviewRequest(BaseModel):
    """Schema for recording a review of a flashcard."""

    rating: FlashcardRatingLiteral = Field(..., description="How well the card was recalled")
    reviewed_at: AwareDatetime = Field(..., description="When the reader gave the rating")


class FlashcardStatusRequest(BaseModel):
    """Schema for suspending or unsuspending a flashcard."""

    status: FlashcardStatusLiteral
