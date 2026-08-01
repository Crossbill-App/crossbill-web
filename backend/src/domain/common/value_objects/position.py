"""Position value object for document-order location tracking.

Position represents a location in a book as (index, char_index).
- For EPUBs: index = document-order element number, char_index = character offset

Supports natural ordering via @dataclass(order=True).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True, order=True)
class Position:
    """A location in a book, comparable by document order."""

    index: int
    char_index: int = 0

    def to_json(self) -> list[int]:
        """Serialize to JSON-compatible list [index, char_index]."""
        return [self.index, self.char_index]

    @classmethod
    def from_json(cls, data: list[int]) -> Self:
        """Deserialize from JSON list [index, char_index]."""
        return cls(index=data[0], char_index=data[1])
