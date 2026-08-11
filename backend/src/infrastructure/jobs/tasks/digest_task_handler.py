"""SAQ task handler for chapter digest generation."""

import structlog
from saq.types import Context

from src.application.reading.commands.chapter_digest.generate_chapter_digest_use_case import (
    GenerateChapterDigestUseCase,
)
from src.domain.common.value_objects.ids import ChapterId, UserId
from src.infrastructure.jobs.tasks.job_context import saq_job_context

logger = structlog.get_logger(__name__)


class DigestTaskHandler:
    def __init__(
        self,
        generate_digest_use_case: GenerateChapterDigestUseCase,
    ) -> None:
        self._generate_use_case = generate_digest_use_case

    async def generate(
        self,
        ctx: Context,
        *,
        batch_id: int,
        book_id: int,
        chapter_id: int,
        user_id: int,
    ) -> None:
        log = logger.bind(
            batch_id=batch_id,
            book_id=book_id,
            chapter_id=chapter_id,
            **saq_job_context(ctx),
        )
        log.info("digest_task_started")
        try:
            await self._generate_use_case.generate_digest(
                chapter_id=ChapterId(chapter_id),
                user_id=UserId(user_id),
            )
        except Exception:
            # Logged here so the failure carries the chapter/book context and
            # traceback as one JSON event; re-raised so SAQ still retries and
            # the batch still counts the failure.
            log.exception("digest_task_failed")
            raise
        log.info("digest_task_completed")
