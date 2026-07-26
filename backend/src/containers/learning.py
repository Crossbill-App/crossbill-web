from dependency_injector import containers, providers

from src.application.learning.queries.get_chapter_flashcard_suggestions_use_case import (
    GetChapterFlashcardSuggestionsUseCase,
)
from src.application.learning.queries.get_flashcard_suggestions_use_case import (
    GetFlashcardSuggestionsUseCase,
)
from src.application.learning.queries.get_flashcards_by_book_use_case import (
    GetFlashcardsByBookUseCase,
)
from src.application.learning.queries.get_note_flashcard_suggestions_use_case import (
    GetNoteFlashcardSuggestionsUseCase,
)
from src.application.learning.use_cases.chat.send_chat_message_use_case import (
    SendChatMessageUseCase,
)
from src.application.learning.use_cases.chat.start_chat_session_use_case import (
    StartChatSessionUseCase,
)
from src.application.learning.use_cases.flashcards.create_flashcard_for_book_use_case import (
    CreateFlashcardForBookUseCase,
)
from src.application.learning.use_cases.flashcards.create_flashcard_for_highlight_use_case import (
    CreateFlashcardForHighlightUseCase,
)
from src.application.learning.use_cases.flashcards.create_flashcard_for_note_use_case import (
    CreateFlashcardForNoteUseCase,
)
from src.application.learning.use_cases.flashcards.delete_flashcard_use_case import (
    DeleteFlashcardUseCase,
)
from src.application.learning.use_cases.flashcards.update_flashcard_use_case import (
    UpdateFlashcardUseCase,
)
from src.application.learning.use_cases.quiz.send_quiz_message_use_case import (
    SendQuizMessageUseCase,
)
from src.application.learning.use_cases.quiz.start_quiz_session_use_case import (
    StartQuizSessionUseCase,
)


class LearningContainer(containers.DeclarativeContainer):
    """Learning module use cases and read models."""

    # Dependencies from shared
    flashcard_repository = providers.Dependency()
    highlight_repository = providers.Dependency()
    book_repository = providers.Dependency()
    chapter_repository = providers.Dependency()
    chapter_prereading_repository = providers.Dependency()
    file_repository = providers.Dependency()
    ebook_text_extraction_service = providers.Dependency()
    ai_service = providers.Dependency()
    ai_chat_session_repository = providers.Dependency()
    note_repository = providers.Dependency()

    # Read models: the query adapter (a port implementation) plus the read use
    # cases that routers call, mirroring how commands are exposed.
    book_flashcard_query = providers.Dependency()

    # Flashcards
    create_flashcard_for_highlight_use_case = providers.Factory(
        CreateFlashcardForHighlightUseCase,
        flashcard_repository=flashcard_repository,
        highlight_repository=highlight_repository,
    )
    create_flashcard_for_book_use_case = providers.Factory(
        CreateFlashcardForBookUseCase,
        flashcard_repository=flashcard_repository,
        book_repository=book_repository,
        chapter_repository=chapter_repository,
    )
    create_flashcard_for_note_use_case = providers.Factory(
        CreateFlashcardForNoteUseCase,
        flashcard_repository=flashcard_repository,
        note_repository=note_repository,
    )
    get_flashcards_by_book_use_case = providers.Factory(
        GetFlashcardsByBookUseCase,
        book_flashcard_query=book_flashcard_query,
        book_repository=book_repository,
    )
    update_flashcard_use_case = providers.Factory(
        UpdateFlashcardUseCase,
        flashcard_repository=flashcard_repository,
    )
    delete_flashcard_use_case = providers.Factory(
        DeleteFlashcardUseCase,
        flashcard_repository=flashcard_repository,
    )

    # Flashcard suggestions
    get_flashcard_suggestions_use_case = providers.Factory(
        GetFlashcardSuggestionsUseCase,
        highlight_repository=highlight_repository,
        ai_flashcard_service=ai_service,
    )
    get_chapter_flashcard_suggestions_use_case = providers.Factory(
        GetChapterFlashcardSuggestionsUseCase,
        chapter_prereading_repository=chapter_prereading_repository,
        ai_flashcard_service=ai_service,
    )
    get_note_flashcard_suggestions_use_case = providers.Factory(
        GetNoteFlashcardSuggestionsUseCase,
        note_repository=note_repository,
        highlight_repository=highlight_repository,
        ai_flashcard_service=ai_service,
    )

    # Quiz
    start_quiz_session_use_case = providers.Factory(
        StartQuizSessionUseCase,
        ai_chat_session_repository=ai_chat_session_repository,
        chapter_repo=chapter_repository,
        book_repo=book_repository,
        file_repo=file_repository,
        text_extraction_service=ebook_text_extraction_service,
        ai_quiz_service=ai_service,
    )
    send_quiz_message_use_case = providers.Factory(
        SendQuizMessageUseCase,
        ai_chat_session_repository=ai_chat_session_repository,
        ai_quiz_service=ai_service,
    )

    # Chat
    start_chat_session_use_case = providers.Factory(
        StartChatSessionUseCase,
        ai_chat_session_repository=ai_chat_session_repository,
        chapter_repo=chapter_repository,
        book_repo=book_repository,
        file_repo=file_repository,
        text_extraction_service=ebook_text_extraction_service,
        ai_chat_service=ai_service,
    )
    send_chat_message_use_case = providers.Factory(
        SendChatMessageUseCase,
        ai_chat_session_repository=ai_chat_session_repository,
        ai_chat_service=ai_service,
    )
