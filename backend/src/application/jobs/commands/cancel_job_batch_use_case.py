"""Use case for cancelling a job batch."""

import structlog

from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.protocols.job_queue_service import JobQueueServiceProtocol
from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.entities.job_batch import JobBatch
from src.domain.jobs.exceptions import JobBatchNotFoundError

logger = structlog.get_logger(__name__)


class CancelJobBatchUseCase:
    def __init__(
        self,
        batch_repo: JobBatchRepositoryProtocol,
        queue_service: JobQueueServiceProtocol,
    ) -> None:
        self._batch_repo = batch_repo
        self._queue_service = queue_service

    async def execute(self, batch_id: JobBatchId, user_id: UserId) -> JobBatch:
        batch = await self._batch_repo.find_by_id(batch_id, user_id)
        if not batch:
            raise JobBatchNotFoundError(batch_id.value)

        for key in batch.job_keys:
            await self._queue_service.abort(key)

        batch.cancel()
        batch = await self._batch_repo.save(batch)

        logger.info("job_batch_cancelled", batch_id=batch_id.value)
        return batch
