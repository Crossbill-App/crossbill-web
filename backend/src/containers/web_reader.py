from dependency_injector import containers, providers

from src.application.web_reader.queries.get_publication_positions_use_case import (
    GetPublicationPositionsUseCase,
)
from src.application.web_reader.queries.get_publication_use_case import GetPublicationUseCase


class WebReaderContainer(containers.DeclarativeContainer):
    """Web reader module use cases and read models."""

    # Dependencies from shared
    publication_repository = providers.Dependency()
    book_repository = providers.Dependency()
    file_repository = providers.Dependency()
    publication_parser = providers.Dependency()

    # Read models
    get_publication_use_case = providers.Factory(
        GetPublicationUseCase,
        publication_repository=publication_repository,
        book_repository=book_repository,
        file_repository=file_repository,
        publication_parser=publication_parser,
    )
    get_publication_positions_use_case = providers.Factory(
        GetPublicationPositionsUseCase,
        get_publication_use_case=get_publication_use_case,
    )
