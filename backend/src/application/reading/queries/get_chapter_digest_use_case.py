"""Use case for retrieving a chapter's digest."""

from src.application.library.protocols.chapter_repository import (
    ChapterRepositoryProtocol,
)
from src.application.reading.protocols.chapter_digest_repository import (
    ChapterDigestRepositoryProtocol,
)
from src.domain.common.value_objects.ids import ChapterId, UserId
from src.domain.reading.entities.chapter_digest import (
    ChapterDigest,
)
from src.domain.reading.exceptions import ChapterNotFoundError


class GetChapterDigestUseCase:
    """Use case for retrieving a chapter's digest."""

    def __init__(
        self,
        digest_repo: ChapterDigestRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
    ) -> None:
        self.digest_repo = digest_repo
        self.chapter_repo = chapter_repo

    async def get_digest(self, chapter_id: ChapterId, user_id: UserId) -> ChapterDigest | None:
        """Get a chapter's existing digest."""
        chapter = await self.chapter_repo.find_by_id(chapter_id, user_id)
        if not chapter:
            raise ChapterNotFoundError(chapter_id.value)

        return await self.digest_repo.find_by_chapter_id(chapter_id)
