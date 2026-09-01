"""Read use case for the reader's latest highlights and notes."""

from datetime import tzinfo

from src.application.reading.queries.recent_captures import (
    RecentCapturesQueryProtocol,
    RecentCaptureView,
)
from src.domain.common.value_objects import UserId


class GetRecentCapturesUseCase:
    """Serve the newest highlights and notes from across the reader's library."""

    def __init__(self, recent_captures_query: RecentCapturesQueryProtocol) -> None:
        self.recent_captures_query = recent_captures_query

    async def get_recent_captures(
        self, user_id: int, zone: tzinfo, limit: int
    ) -> tuple[RecentCaptureView, ...]:
        """Return the reader's newest captures, newest first."""
        return await self.recent_captures_query.get_recent_captures(UserId(user_id), zone, limit)
