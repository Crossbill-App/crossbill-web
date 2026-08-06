"""Jobs domain exceptions."""

from src.domain.common.exceptions import ConflictError, EntityNotFoundError
from src.domain.jobs.entities.job_batch import JobBatchType


class JobBatchNotFoundError(EntityNotFoundError):
    """Raised when a job batch cannot be found."""

    def __init__(self, batch_id: int) -> None:
        super().__init__("JobBatch", batch_id)


class ActiveJobBatchExistsError(ConflictError):
    """Raised when a batch type limited to one active run already has one."""

    def __init__(self, batch_type: JobBatchType) -> None:
        super().__init__(
            f"An active {batch_type.value} batch already exists",
            {"batch_type": batch_type.value},
        )
        self.batch_type = batch_type
