"""
HighlightStyle entity.

Represents a device highlight style (color + drawing style combination)
with optional user-assigned label and UI color.
"""

from __future__ import annotations

import datetime as dt_module
from dataclasses import dataclass, field
from datetime import UTC
from typing import Final

from src.domain.common.entity import Entity
from src.domain.common.value_objects import (
    BookId,
    HighlightStyleId,
    UserId,
)

# The drawer KOReader uses unless the reader picked another.
KOREADER_DEFAULT_DRAWER: Final = "lighten"


@dataclass
class HighlightStyle(Entity[HighlightStyleId]):
    """
    Highlight style entity.

    Represents a device highlight style that users can label and color.
    Rows with both device_color and device_style set are combination-level
    and serve as FK targets for highlights. Rows with one NULL dimension
    are individual-level and participate in label resolution only.
    Rows with book_id=None are global defaults.
    """

    id: HighlightStyleId
    user_id: UserId
    book_id: BookId | None
    device_color: str | None
    device_style: str | None
    label: str | None = None
    ui_color: str | None = None
    created_at: dt_module.datetime = field(default_factory=lambda: dt_module.datetime.now(UTC))
    updated_at: dt_module.datetime = field(default_factory=lambda: dt_module.datetime.now(UTC))

    def update_label(self, label: str | None) -> None:
        """Set or clear the user-assigned label."""
        self.label = label.strip() if label else None
        self.updated_at = dt_module.datetime.now(UTC)

    def update_ui_color(self, ui_color: str | None) -> None:
        """Set or clear the user-chosen UI color."""
        self.ui_color = ui_color
        self.updated_at = dt_module.datetime.now(UTC)

    def is_combination_level(self) -> bool:
        """Check if both device fields are set (combination-level style)."""
        return self.device_color is not None and self.device_style is not None

    def is_global(self) -> bool:
        """Check if this is a global default (no book_id)."""
        return self.book_id is None

    @classmethod
    def create(
        cls,
        user_id: UserId,
        book_id: BookId | None,
        device_color: str | None,
        device_style: str | None,
        label: str | None = None,
        ui_color: str | None = None,
    ) -> HighlightStyle:
        """Factory for creating a new highlight style."""
        now = dt_module.datetime.now(UTC)
        return cls(
            id=HighlightStyleId.generate(),
            user_id=user_id,
            book_id=book_id,
            device_color=device_color,
            device_style=device_style,
            label=label,
            ui_color=ui_color,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def create_with_id(
        cls,
        id: HighlightStyleId,
        user_id: UserId,
        book_id: BookId | None,
        device_color: str | None,
        device_style: str | None,
        label: str | None,
        ui_color: str | None,
        created_at: dt_module.datetime,
        updated_at: dt_module.datetime,
    ) -> HighlightStyle:
        """Factory for reconstituting from persistence."""
        return cls(
            id=id,
            user_id=user_id,
            book_id=book_id,
            device_color=device_color,
            device_style=device_style,
            label=label,
            ui_color=ui_color,
            created_at=created_at,
            updated_at=updated_at,
        )
