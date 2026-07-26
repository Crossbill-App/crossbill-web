"""Use case for updating a highlight label."""

from src.application.reading.protocols.highlight_style_repository import (
    HighlightStyleRepositoryProtocol,
)
from src.domain.common.value_objects import HighlightStyleId, UserId
from src.domain.reading.entities.highlight_style import HighlightStyle
from src.domain.reading.exceptions import HighlightStyleNotFoundError


class UpdateHighlightLabelUseCase:
    """Update label and/or ui_color on a highlight style."""

    def __init__(
        self,
        highlight_style_repository: HighlightStyleRepositoryProtocol,
    ) -> None:
        self.highlight_style_repository = highlight_style_repository

    async def execute(
        self,
        style_id: int,
        user_id: int,
        label: str | None = None,
        ui_color: str | None = None,
    ) -> HighlightStyle:
        """Update a highlight style's label and/or ui_color."""
        style = await self.highlight_style_repository.find_by_id(
            HighlightStyleId(style_id), UserId(user_id)
        )
        if not style:
            raise HighlightStyleNotFoundError(style_id)

        if label is not None:
            style.update_label(label)
        if ui_color is not None:
            style.update_ui_color(ui_color)

        return await self.highlight_style_repository.save(style)
