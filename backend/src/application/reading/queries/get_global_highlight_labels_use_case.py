"""Read use case for the user's global highlight-label defaults."""

from src.application.reading.queries.highlight_labels import (
    HighlightLabelQueryProtocol,
    HighlightLabelView,
)
from src.domain.common.value_objects import UserId


class GetGlobalHighlightLabelsUseCase:
    """Serve the user's global default highlight labels."""

    def __init__(self, highlight_label_query: HighlightLabelQueryProtocol) -> None:
        self.highlight_label_query = highlight_label_query

    async def execute(self, user_id: int) -> tuple[HighlightLabelView, ...]:
        """Return the user's global highlight labels."""
        return await self.highlight_label_query.list_global(UserId(user_id))
