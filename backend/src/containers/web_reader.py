from dependency_injector import containers, providers

from src.application.web_reader.queries.get_web_publication_use_case import (
    GetWebPublicationUseCase,
)


class WebReaderContainer(containers.DeclarativeContainer):
    """Web reader module use cases."""

    # Dependencies from shared
    web_publication_query = providers.Dependency()

    get_web_publication_use_case = providers.Factory(
        GetWebPublicationUseCase,
        web_publication_query=web_publication_query,
    )
