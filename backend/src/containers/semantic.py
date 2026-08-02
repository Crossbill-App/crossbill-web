"""DI container for the semantic (embeddings) context."""

from dependency_injector import containers, providers

from src.application.semantic.commands.enqueue_content_embeddings_use_case import (
    EnqueueContentEmbeddingsUseCase,
)
from src.application.semantic.commands.generate_content_embedding_use_case import (
    GenerateContentEmbeddingUseCase,
)
from src.application.semantic.queries.related_content_use_case import RelatedContentUseCase
from src.application.semantic.queries.search_content_use_case import SearchContentUseCase


class SemanticContainer(containers.DeclarativeContainer):
    """Container for semantic-search use cases."""

    content_source = providers.Dependency()
    embedding_repository = providers.Dependency()
    embedding_client = providers.Dependency()
    settings = providers.Dependency()
    job_batch_repository = providers.Dependency()
    job_queue_service = providers.Dependency()
    book_repository = providers.Dependency()
    semantic_search_query = providers.Dependency()

    generate_content_embedding_use_case = providers.Factory(
        GenerateContentEmbeddingUseCase,
        content_source=content_source,
        client=embedding_client,
        repo=embedding_repository,
        settings=settings,
    )

    enqueue_content_embeddings_use_case = providers.Factory(
        EnqueueContentEmbeddingsUseCase,
        content_source=content_source,
        batch_repo=job_batch_repository,
        queue_service=job_queue_service,
        book_repo=book_repository,
    )

    search_content_use_case = providers.Factory(
        SearchContentUseCase,
        query=semantic_search_query,
        client=embedding_client,
        content_source=content_source,
    )

    related_content_use_case = providers.Factory(
        RelatedContentUseCase,
        query=semantic_search_query,
        content_source=content_source,
    )
