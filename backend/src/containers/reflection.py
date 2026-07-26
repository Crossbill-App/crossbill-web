from dependency_injector import containers, providers

from src.application.reflection.commands.upsert_book_reflection_use_case import (
    UpsertBookReflectionUseCase,
)
from src.application.reflection.queries.get_book_reflection_use_case import (
    GetBookReflectionUseCase,
)


class ReflectionContainer(containers.DeclarativeContainer):
    """Reflection module use cases."""

    # Dependencies from shared
    book_reflection_repository = providers.Dependency()
    book_repository = providers.Dependency()
    note_repository = providers.Dependency()

    get_book_reflection_use_case = providers.Factory(
        GetBookReflectionUseCase,
        book_reflection_repository=book_reflection_repository,
        book_repository=book_repository,
    )
    upsert_book_reflection_use_case = providers.Factory(
        UpsertBookReflectionUseCase,
        book_reflection_repository=book_reflection_repository,
        book_repository=book_repository,
        note_repository=note_repository,
    )
