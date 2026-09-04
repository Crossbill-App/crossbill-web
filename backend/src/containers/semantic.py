"""DI container for the semantic (embeddings) context."""

from dependency_injector import containers, providers

from src.application.semantic.commands.enqueue_content_embeddings_use_case import (
    EnqueueContentEmbeddingsUseCase,
)
from src.application.semantic.queries.global_search_use_case import GlobalSearchUseCase
from src.application.semantic.queries.related_content_use_case import RelatedContentUseCase


class SemanticContainer(containers.DeclarativeContainer):
    """Container for semantic-search use cases."""

    content_source = providers.Dependency()
    embedding_client = providers.Dependency()
    job_batch_repository = providers.Dependency()
    job_queue_service = providers.Dependency()
    book_repository = providers.Dependency()
    semantic_search_query = providers.Dependency()
    search_hydration_query = providers.Dependency()
    book_list_query = providers.Dependency()

    enqueue_content_embeddings_use_case = providers.Factory(
        EnqueueContentEmbeddingsUseCase,
        content_source=content_source,
        batch_repo=job_batch_repository,
        queue_service=job_queue_service,
        book_repo=book_repository,
    )

    global_search_use_case = providers.Factory(
        GlobalSearchUseCase,
        query=semantic_search_query,
        client=embedding_client,
        hydration=search_hydration_query,
        books=book_list_query,
    )

    related_content_use_case = providers.Factory(
        RelatedContentUseCase,
        query=semantic_search_query,
        hydration=search_hydration_query,
    )
