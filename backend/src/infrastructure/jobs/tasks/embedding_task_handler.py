"""SAQ task handler for content embedding generation."""

import structlog
from saq.types import Context

from src.application.semantic.commands.generate_content_embedding_use_case import (
    GenerateContentEmbeddingUseCase,
)
from src.application.semantic.content_type import ContentType

logger = structlog.get_logger(__name__)


class EmbeddingTaskHandler:
    def __init__(
        self,
        generate_embedding_use_case: GenerateContentEmbeddingUseCase,
    ) -> None:
        self._generate_use_case = generate_embedding_use_case

    async def generate(
        self,
        _ctx: Context,
        *,
        content_type: ContentType,
        content_id: int,
        batch_id: int | None = None,
    ) -> None:
        logger.info(
            "embedding_task_started",
            batch_id=batch_id,
            content_type=content_type.value,
            content_id=content_id,
        )
        await self._generate_use_case.execute(content_type=content_type, content_id=content_id)
        logger.info(
            "embedding_task_completed",
            batch_id=batch_id,
            content_type=content_type.value,
            content_id=content_id,
        )
