from dependency_injector import containers, providers

from src.application.reading.commands.bookmarks.create_bookmark_use_case import (
    CreateBookmarkUseCase,
)
from src.application.reading.commands.bookmarks.delete_bookmark_use_case import (
    DeleteBookmarkUseCase,
)
from src.application.reading.commands.chapter_prereading.generate_chapter_prereading_use_case import (
    GenerateChapterPrereadingUseCase,
)
from src.application.reading.commands.chapter_prereading.update_prereading_answers_use_case import (
    UpdatePrereadingAnswersUseCase,
)
from src.application.reading.commands.highlight_labels.create_global_highlight_label_use_case import (
    CreateGlobalHighlightLabelUseCase,
)
from src.application.reading.commands.highlight_labels.update_highlight_label_use_case import (
    UpdateHighlightLabelUseCase,
)
from src.application.reading.commands.highlights.highlight_delete_use_case import (
    HighlightDeleteUseCase,
)
from src.application.reading.commands.highlights.highlight_upload_use_case import (
    HighlightUploadUseCase,
)
from src.application.reading.commands.reading_sessions.reading_session_ai_summary_use_case import (
    ReadingSessionAISummaryUseCase,
)
from src.application.reading.commands.reading_sessions.reading_session_upload_use_case import (
    ReadingSessionUploadUseCase,
)
from src.application.reading.commands.tag_associations.add_tag_to_highlight_by_id_use_case import (
    AddTagToHighlightByIdUseCase,
)
from src.application.reading.commands.tag_associations.add_tag_to_highlight_by_name_use_case import (
    AddTagToHighlightByNameUseCase,
)
from src.application.reading.commands.tag_associations.remove_tag_from_highlight_use_case import (
    RemoveTagFromHighlightUseCase,
)
from src.application.reading.queries.chapter_content_use_case import (
    ChapterContentUseCase,
)
from src.application.reading.queries.get_book_highlight_labels_use_case import (
    GetBookHighlightLabelsUseCase,
)
from src.application.reading.queries.get_book_prereading_use_case import (
    GetBookPrereadingUseCase,
)
from src.application.reading.queries.get_book_reading_sessions_use_case import (
    ReadingSessionQueryUseCase,
)
from src.application.reading.queries.get_bookmarks_use_case import (
    GetBookmarksUseCase,
)
from src.application.reading.queries.get_chapter_prereading_use_case import (
    GetChapterPrereadingUseCase,
)
from src.application.reading.queries.get_ereader_book_prereading_use_case import (
    GetEreaderBookPrereadingUseCase,
)
from src.application.reading.queries.get_global_highlight_labels_use_case import (
    GetGlobalHighlightLabelsUseCase,
)
from src.application.reading.queries.highlight_search_use_case import (
    HighlightSearchUseCase,
)


class ReadingContainer(containers.DeclarativeContainer):
    """Reading module use cases."""

    # Dependencies from shared
    book_repository = providers.Dependency()
    bookmark_repository = providers.Dependency()
    highlight_repository = providers.Dependency()
    tag_repository = providers.Dependency()
    chapter_repository = providers.Dependency()
    reading_session_repository = providers.Dependency()
    chapter_prereading_repository = providers.Dependency()
    highlight_style_repository = providers.Dependency()
    file_repository = providers.Dependency()
    highlight_deduplication_service = providers.Dependency()
    label_resolution_service = providers.Dependency()
    epub_position_index_service = providers.Dependency()
    ebook_text_extraction_service = providers.Dependency()
    ai_service = providers.Dependency()

    # Query services (read models)
    bookmark_query = providers.Dependency()
    highlight_label_query = providers.Dependency()
    highlight_search_query = providers.Dependency()
    reading_session_query = providers.Dependency()
    ereader_prereading_query = providers.Dependency()

    # Bookmarks
    create_bookmark_use_case = providers.Factory(
        CreateBookmarkUseCase,
        book_repository=book_repository,
        bookmark_repository=bookmark_repository,
        highlight_repository=highlight_repository,
    )
    delete_bookmark_use_case = providers.Factory(
        DeleteBookmarkUseCase,
        book_repository=book_repository,
        bookmark_repository=bookmark_repository,
    )
    get_bookmarks_use_case = providers.Factory(
        GetBookmarksUseCase,
        bookmark_query=bookmark_query,
    )

    # Highlights
    highlight_search_use_case = providers.Factory(
        HighlightSearchUseCase,
        highlight_search_query=highlight_search_query,
    )
    highlight_delete_use_case = providers.Factory(
        HighlightDeleteUseCase,
        book_repository=book_repository,
        highlight_repository=highlight_repository,
    )
    highlight_upload_use_case = providers.Factory(
        HighlightUploadUseCase,
        highlight_repository=highlight_repository,
        book_repository=book_repository,
        chapter_repository=chapter_repository,
        deduplication_service=highlight_deduplication_service,
        position_index_service=epub_position_index_service,
        file_repository=file_repository,
        highlight_style_repository=highlight_style_repository,
    )

    # Tag associations
    add_tag_to_highlight_by_id_use_case = providers.Factory(
        AddTagToHighlightByIdUseCase,
        highlight_repository=highlight_repository,
        tag_repository=tag_repository,
        label_resolution_service=label_resolution_service,
    )
    add_tag_to_highlight_by_name_use_case = providers.Factory(
        AddTagToHighlightByNameUseCase,
        highlight_repository=highlight_repository,
        tag_repository=tag_repository,
        label_resolution_service=label_resolution_service,
    )
    remove_tag_from_highlight_use_case = providers.Factory(
        RemoveTagFromHighlightUseCase,
        highlight_repository=highlight_repository,
        label_resolution_service=label_resolution_service,
    )

    # Highlight labels
    get_book_highlight_labels_use_case = providers.Factory(
        GetBookHighlightLabelsUseCase,
        highlight_label_query=highlight_label_query,
    )
    update_highlight_label_use_case = providers.Factory(
        UpdateHighlightLabelUseCase,
        highlight_style_repository=highlight_style_repository,
    )
    get_global_highlight_labels_use_case = providers.Factory(
        GetGlobalHighlightLabelsUseCase,
        highlight_label_query=highlight_label_query,
    )
    create_global_highlight_label_use_case = providers.Factory(
        CreateGlobalHighlightLabelUseCase,
        highlight_style_repository=highlight_style_repository,
    )

    # Reading sessions
    reading_session_upload_use_case = providers.Factory(
        ReadingSessionUploadUseCase,
        session_repository=reading_session_repository,
        book_repository=book_repository,
        highlight_repository=highlight_repository,
        position_index_service=epub_position_index_service,
        file_repository=file_repository,
    )
    reading_session_query_use_case = providers.Factory(
        ReadingSessionQueryUseCase,
        reading_session_query=reading_session_query,
    )
    reading_session_ai_summary_use_case = providers.Factory(
        ReadingSessionAISummaryUseCase,
        session_repository=reading_session_repository,
        text_extraction_service=ebook_text_extraction_service,
        book_repo=book_repository,
        file_repo=file_repository,
        ai_summary_service=ai_service,
    )

    # Chapter prereading
    get_chapter_prereading_use_case = providers.Factory(
        GetChapterPrereadingUseCase,
        prereading_repo=chapter_prereading_repository,
        chapter_repo=chapter_repository,
    )
    get_book_prereading_use_case = providers.Factory(
        GetBookPrereadingUseCase,
        prereading_repo=chapter_prereading_repository,
        chapter_repo=chapter_repository,
    )
    get_ereader_book_prereading_use_case = providers.Factory(
        GetEreaderBookPrereadingUseCase,
        ereader_prereading_query=ereader_prereading_query,
    )
    generate_chapter_prereading_use_case = providers.Factory(
        GenerateChapterPrereadingUseCase,
        prereading_repo=chapter_prereading_repository,
        chapter_repo=chapter_repository,
        text_extraction_service=ebook_text_extraction_service,
        book_repo=book_repository,
        file_repo=file_repository,
        ai_prereading_service=ai_service,
    )
    update_prereading_answers_use_case = providers.Factory(
        UpdatePrereadingAnswersUseCase,
        prereading_repo=chapter_prereading_repository,
        chapter_repo=chapter_repository,
    )

    # Chapter content
    chapter_content_use_case = providers.Factory(
        ChapterContentUseCase,
        chapter_repo=chapter_repository,
        book_repo=book_repository,
        file_repo=file_repository,
        text_extraction_service=ebook_text_extraction_service,
    )
