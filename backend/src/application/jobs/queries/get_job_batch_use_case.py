"""Read use case for retrieving a job batch."""

from src.application.jobs.queries.job_batch import JobBatchQueryProtocol, JobBatchView
from src.domain.common.value_objects.ids import JobBatchId, UserId
from src.domain.jobs.exceptions import JobBatchNotFoundError


class GetJobBatchUseCase:
    def __init__(self, job_batch_query: JobBatchQueryProtocol) -> None:
        self._job_batch_query = job_batch_query

    async def execute(self, batch_id: JobBatchId, user_id: UserId) -> JobBatchView:
        view = await self._job_batch_query.get_batch(batch_id, user_id)
        if not view:
            raise JobBatchNotFoundError(batch_id.value)
        return view
