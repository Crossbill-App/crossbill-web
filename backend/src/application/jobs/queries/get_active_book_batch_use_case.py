"""Read use case for finding an active job batch for a book."""

from src.application.jobs.queries.job_batch import JobBatchQueryProtocol, JobBatchView
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.jobs.entities.job_batch import JobBatchType


class GetActiveBookBatchUseCase:
    def __init__(self, job_batch_query: JobBatchQueryProtocol) -> None:
        self._job_batch_query = job_batch_query

    async def execute(
        self, book_id: BookId, user_id: UserId, batch_type: JobBatchType
    ) -> JobBatchView | None:
        return await self._job_batch_query.get_active_for_reference(
            batch_type=batch_type,
            reference_id=str(book_id.value),
            user_id=user_id,
        )
