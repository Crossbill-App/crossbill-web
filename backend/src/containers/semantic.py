"""DI container for the semantic (embeddings) context."""

from dependency_injector import containers, providers

from src.application.semantic.commands.enqueue_content_embeddings_use_case import (
    EnqueueContentEmbeddingsUseCase,
)


class SemanticContainer(containers.DeclarativeContainer):
    """Container for semantic-search use cases."""

    content_source = providers.Dependency()
    embedding_client = providers.Dependency()
    job_batch_repository = providers.Dependency()
    job_queue_service = providers.Dependency()
    book_repository = providers.Dependency()

    enqueue_content_embeddings_use_case = providers.Factory(
        EnqueueContentEmbeddingsUseCase,
        content_source=content_source,
        batch_repo=job_batch_repository,
        queue_service=job_queue_service,
        book_repo=book_repository,
    )
