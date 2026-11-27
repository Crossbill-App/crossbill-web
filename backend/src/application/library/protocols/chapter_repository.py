"""Protocol for Chapter repository in library context."""

from typing import Protocol

from src.domain.common.value_objects.ids import BookId, ChapterId, UserId
from src.domain.library.entities.chapter import Chapter, TocChapter


class ChapterRepositoryProtocol(Protocol):
    """Protocol for Chapter repository operations in library context."""

    async def find_by_id(self, chapter_id: ChapterId, user_id: UserId) -> Chapter | None:
        """Find a chapter by ID with ownership verification."""
        ...

    async def find_by_ids(self, chapter_ids: list[int], user_id: UserId) -> list[Chapter]:
        """Find chapters by ids with ownership verification."""
        ...

    async def find_all_by_book(self, book_id: BookId, user_id: UserId) -> list[Chapter]:
        """Find all chapters for a book, ordered by chapter_number."""
        ...

    async def set_start_offsets(self, offsets: dict[ChapterId, int]) -> None:
        """Stage each chapter's start offset; the next commit stores them."""
        ...

    async def sync_chapters_from_toc(
        self,
        book_id: BookId,
        user_id: UserId,
        chapters: list[TocChapter],
    ) -> int:
        """
        Synchronize chapters from TOC data, creating new and updating existing chapters.

        This method handles bulk chapter creation/update from EPUB TOC parsing.
        It preserves hierarchical parent-child relationships and handles duplicates.

        Args:
            book_id: ID of the book
            user_id: ID of the user (for ownership verification)
            chapters: List of TocChapter objects from EPUB TOC parsing

        Returns:
            Number of chapters created (not including updates)
        """
        ...
