"""DI container for jobs module."""

from dependency_injector import containers, providers

from src.application.jobs.commands.cancel_job_batch_use_case import CancelJobBatchUseCase
from src.application.jobs.commands.enqueue_book_digests_use_case import (
    EnqueueBookDigestsUseCase,
)
from src.application.jobs.queries.get_active_book_batch_use_case import (
    GetActiveBookBatchUseCase,
)
from src.application.jobs.queries.get_active_user_batch_use_case import (
    GetActiveUserBatchUseCase,
)
from src.application.jobs.queries.get_job_batch_use_case import GetJobBatchUseCase


class JobsContainer(containers.DeclarativeContainer):
    """Container for job-related use cases."""

    job_batch_repository = providers.Dependency()
    job_batch_query = providers.Dependency()
    job_queue_service = providers.Dependency()
    chapter_repository = providers.Dependency()
    book_repository = providers.Dependency()
    chapter_digest_repository = providers.Dependency()

    enqueue_book_digests_use_case = providers.Factory(
        EnqueueBookDigestsUseCase,
        chapter_repo=chapter_repository,
        book_repo=book_repository,
        batch_repo=job_batch_repository,
        queue_service=job_queue_service,
        digest_repo=chapter_digest_repository,
    )

    get_job_batch_use_case = providers.Factory(
        GetJobBatchUseCase,
        job_batch_query=job_batch_query,
    )

    cancel_job_batch_use_case = providers.Factory(
        CancelJobBatchUseCase,
        batch_repo=job_batch_repository,
        queue_service=job_queue_service,
    )

    get_active_book_batch_use_case = providers.Factory(
        GetActiveBookBatchUseCase,
        job_batch_query=job_batch_query,
    )

    get_active_user_batch_use_case = providers.Factory(
        GetActiveUserBatchUseCase,
        job_batch_query=job_batch_query,
    )
