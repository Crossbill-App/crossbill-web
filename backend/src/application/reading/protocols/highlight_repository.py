from typing import Protocol

from src.domain.common.value_objects import ContentHash
from src.domain.common.value_objects.ids import (
    BookId,
    HighlightId,
    TagId,
    UserId,
)
from src.domain.common.value_objects.position import Position
from src.domain.learning.entities import Flashcard
from src.domain.reading import Highlight
from src.domain.tagging import Tag


class HighlightRepositoryProtocol(Protocol):
    async def find_by_id(self, highlight_id: HighlightId, user_id: UserId) -> Highlight | None: ...

    async def find_by_ids(self, highlight_ids: list[int], user_id: UserId) -> list[Highlight]: ...

    async def find_by_id_with_relations(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> tuple[Highlight, list[Flashcard], list[Tag]] | None: ...

    async def find_by_book_id(self, book_id: BookId, user_id: UserId) -> list[Highlight]: ...

    async def count_by_book(self, book_id: BookId, user_id: UserId) -> int: ...

    async def get_existing_hashes(
        self, user_id: UserId, book_id: BookId, hashes: list[ContentHash]
    ) -> set[ContentHash]: ...

    async def save(self, highlight: Highlight) -> Highlight: ...

    async def bulk_save(self, highlights: list[Highlight]) -> list[Highlight]: ...

    async def bulk_update_positions(
        self,
        position_updates: list[tuple[HighlightId, Position]],
    ) -> int: ...

    async def soft_delete_by_ids(
        self,
        highlight_ids: list[HighlightId],
        user_id: UserId,
        book_id: BookId,
    ) -> int: ...

    # Tag associations (owned by reading; tags themselves live in the tagging module)

    async def add_tag_to_highlight(
        self, highlight_id: HighlightId, tag_id: TagId, user_id: UserId
    ) -> bool: ...

    async def remove_tag_from_highlight(
        self, highlight_id: HighlightId, tag_id: TagId, user_id: UserId
    ) -> bool: ...
