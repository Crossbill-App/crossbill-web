from dependency_injector import containers, providers

from src.application.web_reader.queries.get_publication_positions_use_case import (
    GetPublicationPositionsUseCase,
)
from src.application.web_reader.queries.get_publication_resource_use_case import (
    GetPublicationResourceUseCase,
)
from src.application.web_reader.queries.get_web_publication_use_case import (
    GetWebPublicationUseCase,
)
from src.application.web_reader.queries.verify_publication_access_use_case import (
    VerifyPublicationAccessUseCase,
)


class WebReaderContainer(containers.DeclarativeContainer):
    """Web reader module use cases."""

    # Dependencies from shared
    book_repository = providers.Dependency()
    web_publication_query = providers.Dependency()
    publication_resource_query = providers.Dependency()
    publication_positions_query = providers.Dependency()

    get_web_publication_use_case = providers.Factory(
        GetWebPublicationUseCase,
        web_publication_query=web_publication_query,
    )

    get_publication_resource_use_case = providers.Factory(
        GetPublicationResourceUseCase,
        publication_resource_query=publication_resource_query,
    )

    get_publication_positions_use_case = providers.Factory(
        GetPublicationPositionsUseCase,
        publication_positions_query=publication_positions_query,
    )

    verify_publication_access_use_case = providers.Factory(
        VerifyPublicationAccessUseCase,
        book_repository=book_repository,
    )
