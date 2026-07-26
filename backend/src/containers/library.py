from dependency_injector import containers, providers

from src.application.library.queries.get_book_details_use_case import GetBookDetailsUseCase
from src.application.library.queries.get_books_with_counts_use_case import (
    GetBooksWithCountsUseCase,
)
from src.application.library.queries.get_recently_viewed_books_use_case import (
    GetRecentlyViewedBooksUseCase,
)
from src.application.library.use_cases.book_files.ebook_deletion_use_case import (
    EbookDeletionUseCase,
)
from src.application.library.use_cases.book_files.ebook_upload_use_case import EbookUploadUseCase
from src.application.library.use_cases.book_management.create_book_use_case import (
    CreateBookUseCase,
)
from src.application.library.use_cases.book_management.delete_book_use_case import (
    DeleteBookUseCase,
)
from src.application.library.use_cases.book_management.mark_book_viewed_use_case import (
    MarkBookViewedUseCase,
)
from src.application.library.use_cases.book_management.update_reading_stage_use_case import (
    UpdateReadingStageUseCase,
)
from src.application.library.use_cases.book_queries.get_ereader_metadata_use_case import (
    GetEreaderMetadataUseCase,
)


class LibraryContainer(containers.DeclarativeContainer):
    """Library module use cases and read models."""

    # Dependencies from shared
    book_repository = providers.Dependency()
    chapter_repository = providers.Dependency()
    highlight_repository = providers.Dependency()
    reading_session_repository = providers.Dependency()
    file_repository = providers.Dependency()
    epub_parser_service = providers.Dependency()
    epub_position_index_service = providers.Dependency()
    cover_image_service = providers.Dependency()

    # Read models: the query adapters (port implementations) plus the read use
    # cases that routers call, mirroring how commands are exposed.
    book_details_query = providers.Dependency()
    book_list_query = providers.Dependency()

    # Book files
    ebook_upload_use_case = providers.Factory(
        EbookUploadUseCase,
        book_repository=book_repository,
        chapter_repository=chapter_repository,
        file_repository=file_repository,
        epub_parser=epub_parser_service,
        cover_image_service=cover_image_service,
        position_index_service=epub_position_index_service,
        highlight_repository=highlight_repository,
        session_repository=reading_session_repository,
    )
    ebook_deletion_use_case = providers.Factory(
        EbookDeletionUseCase,
        file_repository=file_repository,
    )

    # Book management
    create_book_use_case = providers.Factory(
        CreateBookUseCase,
        book_repository=book_repository,
    )
    mark_book_viewed_use_case = providers.Factory(
        MarkBookViewedUseCase,
        book_repository=book_repository,
    )
    delete_book_use_case = providers.Factory(
        DeleteBookUseCase,
        book_repository=book_repository,
        ebook_deletion_use_case=ebook_deletion_use_case,
    )
    update_reading_stage_use_case = providers.Factory(
        UpdateReadingStageUseCase,
        book_repository=book_repository,
    )

    # Read models
    get_book_details_use_case = providers.Factory(
        GetBookDetailsUseCase,
        mark_book_viewed_use_case=mark_book_viewed_use_case,
        book_details_query=book_details_query,
    )
    get_books_with_counts_use_case = providers.Factory(
        GetBooksWithCountsUseCase,
        book_list_query=book_list_query,
    )
    get_recently_viewed_books_use_case = providers.Factory(
        GetRecentlyViewedBooksUseCase,
        book_list_query=book_list_query,
    )
    get_ereader_metadata_use_case = providers.Factory(
        GetEreaderMetadataUseCase,
        book_repository=book_repository,
    )
