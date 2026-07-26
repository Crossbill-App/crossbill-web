"""Use case for updating user answers on prereading questions."""

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
from src.domain.reading.exceptions import ChapterNotFoundError, ChapterPrereadingNotFoundError


class UpdatePrereadingAnswersUseCase:
    """Use case for updating user answers on prereading questions."""

    def __init__(
        self,
        prereading_repo: ChapterPrereadingRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
    ) -> None:
        self.prereading_repo = prereading_repo
        self.chapter_repo = chapter_repo

    async def update_answers(
        self,
        chapter_id: ChapterId,
        user_id: UserId,
        answers: dict[int, str],
    ) -> ChapterPrereadingContent:
        """Update user answers for a chapter's prereading questions."""
        # Verify chapter exists and user owns it
        chapter = await self.chapter_repo.find_by_id(chapter_id, user_id)
        if not chapter:
            raise ChapterNotFoundError(chapter_id.value)

        # Load existing prereading content
        content = await self.prereading_repo.find_by_chapter_id(chapter_id)
        if not content:
            raise ChapterPrereadingNotFoundError(chapter_id.value)

        # Update answers and save
        content.update_user_answers(answers)
        return await self.prereading_repo.save(content)
