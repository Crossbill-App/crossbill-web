"""Application-layer DTOs for library module."""

from dataclasses import dataclass


@dataclass
class CreateBookInput:
    """Input data for creating a book."""

    title: str
    client_book_id: str
    author: str | None = None
    isbn: str | None = None
    description: str | None = None
    language: str | None = None
    page_count: int | None = None
