"""Read model for the highlight-label lists.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.

Two endpoints render the same response schema -- a book's labels and the user's
global defaults -- so they share one DTO and one port with a method each.
"""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class HighlightLabelView:
    """A highlight style as a label row.

    ``label_source`` says where the effective label came from; the global list
    is by definition its own source. ``highlight_count`` is counted only for a
    book's labels -- the global list has always reported ``0``, because a global
    style is not what highlights point at.
    """

    id: int
    device_color: str | None
    device_style: str | None
    label: str | None
    ui_color: str | None
    label_source: str
    highlight_count: int


class HighlightLabelQueryProtocol(Protocol):
    """Port for reading highlight-label lists."""

    async def list_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[HighlightLabelView, ...] | None:
        """Return a book's resolved labels, or ``None`` if the user has no such book."""
        ...

    async def list_global(self, user_id: UserId) -> tuple[HighlightLabelView, ...]:
        """Return the user's global default labels."""
        ...
