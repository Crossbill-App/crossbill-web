"""Use case for enqueuing a backfill batch of content embeddings."""

import structlog

from src.application.common.ownership import require_book
from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.semantic.batching import enqueue_embedding_batch, slice_ids
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.content_source import ContentSourceProtocol, PendingUnit
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.jobs.entities.job_batch import JobBatch

logger = structlog.get_logger(__name__)


def _slices(items: list[PendingUnit]) -> list[tuple[ContentType, list[int]]]:
    """Group pending units by content type, then cut each group into job-sized slices.

    One slice never mixes types -- the job resolves its ids through a single
    ``get_embeddable_many`` call, which reads one type's table.
    """
    by_type: dict[ContentType, list[int]] = {}
    for item in items:
        by_type.setdefault(item.content_type, []).append(item.content_id)
    return [
        (content_type, chunk)
        for content_type, content_ids in by_type.items()
        for chunk in slice_ids(content_ids)
    ]


class EnqueueContentEmbeddingsUseCase:
    """Reconciles the user's content against the index and enqueues one job per gap."""

    def __init__(
        self,
        content_source: ContentSourceProtocol,
        batch_repo: JobBatchRepositoryProtocol,
        queue_service: JobQueueServiceProtocol,
        book_repo: BookRepositoryProtocol,
    ) -> None:
        self._content_source = content_source
        self._batch_repo = batch_repo
        self._queue_service = queue_service
        self._book_repo = book_repo

    async def execute(self, user_id: UserId, book_id: BookId | None) -> JobBatch | None:
        if book_id is not None:
            await require_book(self._book_repo, book_id, user_id)

        items_to_generate_embeddings = await self._content_source.find_units_needing_embedding(
            user_id.value, book_id.value if book_id else None
        )
        if not items_to_generate_embeddings:
            return None

        reference_id = str(book_id.value) if book_id else f"user:{user_id.value}"
        batch = await enqueue_embedding_batch(
            _slices(items_to_generate_embeddings),
            user_id=user_id,
            reference_id=reference_id,
            queue_service=self._queue_service,
            batch_repo=self._batch_repo,
        )

        # A button the user pressed: getting nowhere has to be reported.
        if not batch.job_keys:
            raise DomainError("Failed to enqueue any jobs for content embedding")

        logger.info(
            "content_embedding_batch_enqueued",
            batch_id=batch.id.value,
            reference_id=reference_id,
            total_jobs=batch.total_jobs,
        )
        return batch
