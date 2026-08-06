"""Read use case for finding a user's active batch of a given type."""

from src.application.jobs.queries.job_batch import JobBatchQueryProtocol, JobBatchView
from src.domain.common.value_objects.ids import UserId
from src.domain.jobs.entities.job_batch import JobBatchType


class GetActiveUserBatchUseCase:
    def __init__(self, job_batch_query: JobBatchQueryProtocol) -> None:
        self._job_batch_query = job_batch_query

    async def execute(self, user_id: UserId, batch_type: JobBatchType) -> JobBatchView | None:
        return await self._job_batch_query.get_active_for_user(
            batch_type=batch_type,
            user_id=user_id,
        )
