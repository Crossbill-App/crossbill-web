from dependency_injector import containers, providers

from src.application.web_reader.queries.get_publication_use_case import GetPublicationUseCase


class WebReaderContainer(containers.DeclarativeContainer):
    """Web reader module use cases and read models."""

    # Dependencies from shared
    publication_repository = providers.Dependency()
    book_repository = providers.Dependency()

    # Read models
    get_publication_use_case = providers.Factory(
        GetPublicationUseCase,
        publication_repository=publication_repository,
        book_repository=book_repository,
    )
