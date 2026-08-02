"""Pydantic schemas for semantic-search API responses."""

from pydantic import BaseModel

from src.application.semantic.content_type import ContentType


class SemanticSearchResult(BaseModel):
    content_type: ContentType
    content_id: int
    book_id: int | None
    score: float
    text: str
