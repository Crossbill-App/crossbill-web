"""Use case for updating user answers on digest questions."""

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
from src.domain.reading.exceptions import ChapterDigestNotFoundError, ChapterNotFoundError


class UpdateDigestAnswersUseCase:
    """Use case for updating user answers on digest questions."""

    def __init__(
        self,
        digest_repo: ChapterDigestRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
    ) -> None:
        self.digest_repo = digest_repo
        self.chapter_repo = chapter_repo

    async def update_answers(
        self,
        chapter_id: ChapterId,
        user_id: UserId,
        answers: dict[int, str],
    ) -> ChapterDigest:
        """Update user answers for a chapter's digest questions."""
        # Verify chapter exists and user owns it
        chapter = await self.chapter_repo.find_by_id(chapter_id, user_id)
        if not chapter:
            raise ChapterNotFoundError(chapter_id.value)

        # Load the existing digest
        content = await self.digest_repo.find_by_chapter_id(chapter_id)
        if not content:
            raise ChapterDigestNotFoundError(chapter_id.value)

        # Update answers and save
        content.update_user_answers(answers)
        return await self.digest_repo.save(content)
