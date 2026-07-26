from typing import Protocol

from src.domain.common.value_objects.ids import BookId, BookmarkId, HighlightId, UserId
from src.domain.reading.entities.bookmark import Bookmark


class BookmarkRepositoryProtocol(Protocol):
    async def find_by_book_and_highlight(
        self, book_id: BookId, highlight_id: HighlightId
    ) -> Bookmark | None: ...
    async def save(self, bookmark: Bookmark, /) -> Bookmark: ...
    async def delete(self, bookmark_id: BookmarkId, /, user_id: UserId) -> bool: ...
