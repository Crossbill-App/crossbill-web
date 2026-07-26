"""Use case for retrieving prereading content for a chapter."""

from src.application.library.protocols.chapter_repository import (
    ChapterRepositoryProtocol,
)
from src.application.reading.protocols.chapter_prereading_repository import (
    ChapterPrereadingRepositoryProtocol,
)
from src.domain.common.value_objects.ids import ChapterId, UserId
from src.domain.reading.entities.chapter_prereading_content import (
    ChapterPrereadingContent,
)
from src.domain.reading.exceptions import ChapterNotFoundError


class GetChapterPrereadingUseCase:
    """Use case for retrieving prereading content for a chapter."""

    def __init__(
        self,
        prereading_repo: ChapterPrereadingRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
    ) -> None:
        self.prereading_repo = prereading_repo
        self.chapter_repo = chapter_repo

    async def get_prereading_content(
        self, chapter_id: ChapterId, user_id: UserId
    ) -> ChapterPrereadingContent | None:
        """Get existing prereading content for a chapter."""
        chapter = await self.chapter_repo.find_by_id(chapter_id, user_id)
        if not chapter:
            raise ChapterNotFoundError(chapter_id.value)

        return await self.prereading_repo.find_by_chapter_id(chapter_id)
