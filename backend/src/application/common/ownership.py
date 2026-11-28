"""Shared ownership checks used across application use cases.

These helpers collapse the ownership-guard boilerplate that would otherwise be
copy-pasted into every use case: loading a user's book or flashcard (404 when
absent) and asserting that a child entity belongs to the expected book.
"""

from collections.abc import Callable
from typing import Protocol

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, FlashcardId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.learning.exceptions import FlashcardNotFoundError
from src.domain.library.entities.book import Book
from src.domain.reading.exceptions import BookNotFoundError


class _BookByIdLookup(Protocol):
    """Minimal book-repository surface needed to load a book by id."""

    async def find_by_id(self, book_id: BookId, user_id: UserId) -> Book | None: ...


class _BookByClientIdLookup(Protocol):
    """Minimal book-repository surface needed to load a book by client id."""

    async def find_by_client_book_id(self, client_book_id: str, user_id: UserId) -> Book | None: ...


class _FlashcardByIdLookup(Protocol):
    """Minimal flashcard-repository surface needed to load a flashcard by id."""

    async def find_by_id(
        self, flashcard_id: FlashcardId, /, user_id: UserId
    ) -> Flashcard | None: ...


class _BelongsToBook(Protocol):
    """Any child entity that records the book it belongs to."""

    @property
    def book_id(self) -> BookId: ...


async def require_book(
    book_repository: _BookByIdLookup,
    book_id: BookId,
    user_id: UserId,
) -> Book:
    """Load a user's book by id, raising ``BookNotFoundError`` when it is absent."""
    book = await book_repository.find_by_id(book_id, user_id)
    if book is None:
        raise BookNotFoundError(book_id.value)
    return book


async def require_flashcard(
    flashcard_repository: _FlashcardByIdLookup,
    flashcard_id: FlashcardId,
    user_id: UserId,
) -> Flashcard:
    """Load a user's flashcard by id, raising ``FlashcardNotFoundError`` when it is absent."""
    flashcard = await flashcard_repository.find_by_id(flashcard_id, user_id)
    if flashcard is None:
        raise FlashcardNotFoundError(flashcard_id.value)
    return flashcard


async def require_book_by_client_id(
    book_repository: _BookByClientIdLookup,
    client_book_id: str,
    user_id: UserId,
) -> Book:
    """Load a user's book by client id, raising ``BookNotFoundError`` when absent."""
    book = await book_repository.find_by_client_book_id(client_book_id, user_id)
    if book is None:
        raise BookNotFoundError(client_book_id)
    return book


def require_belongs_to_book(
    entity: _BelongsToBook,
    book_id: BookId,
    not_found: Callable[[], DomainError],
) -> None:
    """Assert a child entity belongs to ``book_id``.

    A resource owned by a different book is treated as *not found* (404) rather
    than a validation error (400): from the caller's perspective a resource that
    belongs to someone else's book is indistinguishable from a missing one.
    Callers therefore supply a NotFound exception factory.
    """
    if entity.book_id != book_id:
        raise not_found()
