"""Protocol for Tag and TagGroup repository operations."""

from typing import Protocol

from src.domain.common.value_objects.ids import (
    BookId,
    HighlightId,
    TagGroupId,
    TagId,
    UserId,
)
from src.domain.tagging.entities.tag import Tag
from src.domain.tagging.entities.tag_group import TagGroup


class TagRepositoryProtocol(Protocol):
    """Protocol defining the interface for Tag and TagGroup repository operations."""

    # Tag methods

    async def find_by_id(self, tag_id: TagId, user_id: UserId) -> Tag | None: ...

    async def find_by_book_and_name(
        self, book_id: BookId, name: str, user_id: UserId
    ) -> Tag | None: ...

    async def find_by_book(self, book_id: BookId, user_id: UserId) -> list[Tag]: ...

    async def find_by_ids(self, tag_ids: list[int], user_id: UserId) -> list[Tag]: ...

    async def save(self, tag: Tag) -> Tag: ...

    async def delete(self, tag_id: TagId, user_id: UserId) -> bool: ...

    # Tag group methods

    async def find_groups_by_book(self, book_id: BookId) -> list[TagGroup]: ...

    async def find_group_by_id(self, group_id: TagGroupId, book_id: BookId) -> TagGroup | None: ...

    async def find_group_by_name(self, book_id: BookId, name: str) -> TagGroup | None: ...

    async def save_group(self, group: TagGroup) -> TagGroup: ...

    async def delete_group(self, group_id: TagGroupId) -> bool: ...

    async def check_group_exists(self, group_id: TagGroupId) -> bool: ...

    # Tag-Highlight association methods

    async def add_tag_to_highlight(
        self, highlight_id: HighlightId, tag_id: TagId, user_id: UserId
    ) -> bool: ...

    async def remove_tag_from_highlight(
        self, highlight_id: HighlightId, tag_id: TagId, user_id: UserId
    ) -> bool: ...
