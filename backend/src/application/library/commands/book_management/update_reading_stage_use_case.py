"""Use case for updating a book's manual reading stage."""

import structlog

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import BookId, UserId
from src.domain.library.entities.book import Book, ReadingStage

logger = structlog.get_logger(__name__)


class UpdateReadingStageUseCase:
    """Set (or clear) the manual reading stage on a book."""

    def __init__(self, book_repository: BookRepositoryProtocol) -> None:
        self.book_repository = book_repository

    async def update_reading_stage(
        self,
        book_id: int,
        user_id: int,
        reading_stage: str | None,
    ) -> Book:
        book = await require_book(self.book_repository, BookId(book_id), UserId(user_id))
        book.set_reading_stage(_parse_reading_stage(reading_stage))
        book = await self.book_repository.save(book)
        logger.info("updated_reading_stage", book_id=book_id, reading_stage=reading_stage)
        return book


def _parse_reading_stage(reading_stage: str | None) -> ReadingStage | None:
    """Convert an API stage string to ReadingStage, or raise ValidationError."""
    if reading_stage is None:
        return None
    try:
        return ReadingStage(reading_stage)
    except ValueError as exc:
        raise ValidationError(f"Invalid reading stage: {reading_stage}") from exc
