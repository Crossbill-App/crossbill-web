"""Read model for the Chapter Coverage of a book's chapters.

The coverage is a domain value computed by ``measure_chapter_coverage``, so this
module holds the port alone. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.chapter_coverage import ChapterCoverage


class ChapterCoverageQueryProtocol(Protocol):
    """Port for reading how much of each chapter of a book has been read."""

    async def get_chapter_coverage(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[ChapterCoverage, ...]:
        """Return the coverage of every chapter of a user's book, in reading order."""
        ...
