"""Use case for creating a global highlight label."""

from src.application.reading.protocols.highlight_style_repository import (
    HighlightStyleRepositoryProtocol,
)
from src.domain.common.value_objects import UserId
from src.domain.reading.entities.highlight_style import HighlightStyle


class CreateGlobalHighlightLabelUseCase:
    """Create a global default highlight label."""

    def __init__(
        self,
        highlight_style_repository: HighlightStyleRepositoryProtocol,
    ) -> None:
        self.highlight_style_repository = highlight_style_repository

    async def execute(
        self,
        user_id: int,
        device_color: str | None,
        device_style: str | None,
        label: str | None = None,
        ui_color: str | None = None,
    ) -> HighlightStyle:
        """Create a new global highlight style."""
        style = HighlightStyle.create(
            user_id=UserId(user_id),
            book_id=None,
            device_color=device_color,
            device_style=device_style,
            label=label,
            ui_color=ui_color,
        )
        return await self.highlight_style_repository.save(style)
