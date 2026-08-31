"""Read model for a book's aggregated reading statistics.

The numbers themselves are a domain value -- ``ReadingStatistics``, computed by
``ReadingStatisticsCalculator`` -- so this module holds the port alone. What
comes back exists to be rendered and must never be fed back into a command. See
``docs/adr/0001-read-models-and-query-services.md``.
"""

from datetime import tzinfo
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.reading_statistics_calculator import ReadingStatistics


class BookStatisticsQueryProtocol(Protocol):
    """Port for reading what a book's reading sessions add up to."""

    async def get_statistics(
        self, book_id: BookId, user_id: UserId, zone: tzinfo
    ) -> ReadingStatistics | None:
        """Return the book's statistics, or ``None`` if the user has no such book.

        ``zone`` is the reader's timezone: it decides which calendar day each
        session falls on, and so how many days the reading spanned.
        """
        ...
