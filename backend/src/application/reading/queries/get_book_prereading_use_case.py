"""Use case for retrieving all prereading content for a book."""

from src.application.library.protocols.chapter_repository import (
    ChapterRepositoryProtocol,
)
from src.application.reading.protocols.chapter_prereading_repository import (
    ChapterPrereadingRepositoryProtocol,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.entities.chapter_prereading_content import (
    ChapterPrereadingContent,
)
from src.domain.reading.exceptions import BookNotFoundError


class GetBookPrereadingUseCase:
    """Use case for retrieving all prereading content for a book."""

    def __init__(
        self,
        prereading_repo: ChapterPrereadingRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
    ) -> None:
        self.prereading_repo = prereading_repo
        self.chapter_repo = chapter_repo

    async def get_all_prereading_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> list[ChapterPrereadingContent]:
        """Get all prereading content for chapters in a book."""
        chapters = await self.chapter_repo.find_all_by_book(book_id, user_id)
        if not chapters:
            raise BookNotFoundError(book_id.value)

        return await self.prereading_repo.find_all_by_book_id(book_id)
