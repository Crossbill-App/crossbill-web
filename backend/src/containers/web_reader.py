from dependency_injector import containers, providers

from src.application.web_reader.commands.backfill_book_locators_use_case import (
    BackfillBookLocatorsUseCase,
)
from src.application.web_reader.commands.start_publication_session_use_case import (
    StartPublicationSessionUseCase,
)
from src.application.web_reader.queries.get_publication_positions_use_case import (
    GetPublicationPositionsUseCase,
)
from src.application.web_reader.queries.get_publication_resource_use_case import (
    GetPublicationResourceUseCase,
)
from src.application.web_reader.queries.get_publication_use_case import GetPublicationUseCase


class WebReaderContainer(containers.DeclarativeContainer):
    """Web reader module use cases and read models."""

    # Dependencies from shared
    publication_repository = providers.Dependency()
    book_repository = providers.Dependency()
    file_repository = providers.Dependency()
    publication_parser = providers.Dependency()
    publication_resource_query = providers.Dependency()
    publication_token_service = providers.Dependency()
    highlight_repository = providers.Dependency()
    reading_session_repository = providers.Dependency()
    position_anchor_service = providers.Dependency()

    # Ingest rather than a read: driven by the library module's EPUB upload, and by #841's worker
    backfill_book_locators_use_case = providers.Factory(
        BackfillBookLocatorsUseCase,
        highlight_repository=highlight_repository,
        session_repository=reading_session_repository,
        position_anchor_service=position_anchor_service,
    )

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
    get_publication_resource_use_case = providers.Factory(
        GetPublicationResourceUseCase,
        publication_resource_query=publication_resource_query,
        get_publication_use_case=get_publication_use_case,
    )
    start_publication_session_use_case = providers.Factory(
        StartPublicationSessionUseCase,
        book_repository=book_repository,
        publication_token_service=publication_token_service,
    )
