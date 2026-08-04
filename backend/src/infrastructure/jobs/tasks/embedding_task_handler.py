"""SAQ task handler for content embedding generation."""

import structlog
from saq.types import Context

from src.application.semantic.commands.generate_content_embeddings_use_case import (
    GenerateContentEmbeddingsUseCase,
)
from src.application.semantic.content_type import ContentType

logger = structlog.get_logger(__name__)


class EmbeddingTaskHandler:
    def __init__(
        self,
        generate_embeddings_use_case: GenerateContentEmbeddingsUseCase,
    ) -> None:
        self._generate_use_case = generate_embeddings_use_case

    async def generate(
        self,
        _ctx: Context,
        *,
        content_type: ContentType,
        content_ids: list[int],
        batch_id: int,
    ) -> None:
        log = logger.bind(
            batch_id=batch_id,
            content_type=content_type.value,
            content_ids=content_ids,
            slice_size=len(content_ids),
        )
        log.info("embedding_task_started")
        try:
            await self._generate_use_case.execute(
                content_type=content_type, content_ids=content_ids
            )
        except Exception:
            # A slice fails as a unit, so its ids are the only record of which
            # content to look at -- and one of them is the reason. Logged here,
            # with the traceback, because otherwise the ids live only in the SAQ
            # job record; then re-raised, so the job still retries and the batch
            # still counts the failure.
            log.exception("embedding_task_failed")
            raise
        log.info("embedding_task_completed")
