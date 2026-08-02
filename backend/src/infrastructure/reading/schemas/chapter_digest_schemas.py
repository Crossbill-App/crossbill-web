"""Pydantic schemas for the chapter digest API."""

from datetime import datetime

from pydantic import BaseModel


class DigestQuestionResponse(BaseModel):
    """Response schema for a pre-reading question/answer pair."""

    question: str
    answer: str
    user_answer: str


class DigestAnswerUpdate(BaseModel):
    """Schema for a single answer update."""

    question_index: int
    user_answer: str


class UpdateDigestAnswersRequest(BaseModel):
    """Request schema for updating digest answers."""

    answers: list[DigestAnswerUpdate]


class ChapterDigestResponse(BaseModel):
    """Response schema for a chapter digest."""

    id: int
    chapter_id: int
    summary: str
    keypoints: list[str]
    questions: list[DigestQuestionResponse]
    generated_at: datetime

    model_config = {"from_attributes": True}


class EreaderChapterDigestItem(BaseModel):
    """Ereader-friendly digest for a single chapter.

    Questions are exposed as plain strings only (no AI or user answers) to keep
    the device payload small and preserve active-recall value.
    """

    chapter_id: int
    chapter_name: str
    chapter_number: int | None
    parent_chapter_name: str | None
    summary: str
    keypoints: list[str]
    questions: list[str]
    generated_at: datetime
