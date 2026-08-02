"""SAQ task handler for chapter digest generation."""

import structlog
from saq.types import Context

from src.application.reading.commands.chapter_digest.generate_chapter_digest_use_case import (
    GenerateChapterDigestUseCase,
)
from src.domain.common.value_objects.ids import ChapterId, UserId

logger = structlog.get_logger(__name__)


class DigestTaskHandler:
    def __init__(
        self,
        generate_digest_use_case: GenerateChapterDigestUseCase,
    ) -> None:
        self._generate_use_case = generate_digest_use_case

    async def generate(
        self,
        _ctx: Context,
        *,
        batch_id: int,
        book_id: int,
        chapter_id: int,
        user_id: int,
    ) -> None:
        logger.info(
            "digest_task_started",
            batch_id=batch_id,
            book_id=book_id,
            chapter_id=chapter_id,
        )
        await self._generate_use_case.generate_digest(
            chapter_id=ChapterId(chapter_id),
            user_id=UserId(user_id),
        )
        logger.info(
            "digest_task_completed",
            batch_id=batch_id,
            chapter_id=chapter_id,
        )
