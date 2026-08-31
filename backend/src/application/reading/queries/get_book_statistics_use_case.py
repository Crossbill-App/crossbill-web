"""Read use case for a book's aggregated reading statistics."""

from datetime import date, tzinfo

from src.application.reading.queries.book_statistics import BookStatisticsQueryProtocol
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError
from src.domain.reading.services.reading_statistics_calculator import ReadingStatistics


class GetBookStatisticsUseCase:
    """Serve what a book's reading sessions add up to."""

    def __init__(self, book_statistics_query: BookStatisticsQueryProtocol) -> None:
        self.book_statistics_query = book_statistics_query

    async def get_statistics_for_book(
        self, book_id: int, user_id: int, today: date, zone: tzinfo
    ) -> ReadingStatistics:
        """Return the book's reading statistics, counted in the reader's timezone.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        statistics = await self.book_statistics_query.get_statistics(
            BookId(book_id), UserId(user_id), today, zone
        )
        if statistics is None:
            raise BookNotFoundError(book_id)
        return statistics
