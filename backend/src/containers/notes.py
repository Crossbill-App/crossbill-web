from dependency_injector import containers, providers

from src.application.notes.commands.create_note_use_case import CreateNoteUseCase
from src.application.notes.commands.delete_note_use_case import DeleteNoteUseCase
from src.application.notes.commands.update_note_use_case import UpdateNoteUseCase
from src.application.notes.queries.get_note_use_case import GetNoteUseCase
from src.application.notes.queries.get_notes_by_book_use_case import GetNotesByBookUseCase


class NotesContainer(containers.DeclarativeContainer):
    """Notes module use cases and read models."""

    # Dependencies from shared
    note_repository = providers.Dependency()
    book_repository = providers.Dependency()
    chapter_repository = providers.Dependency()
    highlight_repository = providers.Dependency()
    tag_repository = providers.Dependency()
    embedding_enqueuer = providers.Dependency()

    # Read models: the query adapter (a port implementation) plus the read use
    # cases that routers call, mirroring how commands are exposed.
    note_query = providers.Dependency()

    create_note_use_case = providers.Factory(
        CreateNoteUseCase,
        note_repository=note_repository,
        book_repository=book_repository,
        chapter_repository=chapter_repository,
        highlight_repository=highlight_repository,
        tag_repository=tag_repository,
        embedding_enqueuer=embedding_enqueuer,
    )
    get_note_use_case = providers.Factory(
        GetNoteUseCase,
        note_query=note_query,
    )
    get_notes_by_book_use_case = providers.Factory(
        GetNotesByBookUseCase,
        note_query=note_query,
        book_repository=book_repository,
    )
    update_note_use_case = providers.Factory(
        UpdateNoteUseCase,
        note_repository=note_repository,
        chapter_repository=chapter_repository,
        highlight_repository=highlight_repository,
        tag_repository=tag_repository,
        embedding_enqueuer=embedding_enqueuer,
    )
    delete_note_use_case = providers.Factory(
        DeleteNoteUseCase,
        note_repository=note_repository,
    )
