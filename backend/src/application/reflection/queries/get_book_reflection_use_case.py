"""Use case for reading a book's reflection."""

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.reflection.protocols.book_reflection_repository import (
    BookReflectionRepositoryProtocol,
)
from src.domain.common.value_objects import BookId, UserId
from src.domain.reflection.entities.book_reflection import BookReflection


class GetBookReflectionUseCase:
    """Return a book's reflection, or a transient empty default when none exists."""

    def __init__(
        self,
        book_reflection_repository: BookReflectionRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.book_reflection_repository = book_reflection_repository
        self.book_repository = book_repository

    async def get_reflection(self, book_id: int, user_id: int) -> BookReflection:
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        reflection = await self.book_reflection_repository.find_by_book_id(book_id_vo, user_id_vo)
        if reflection is None:
            return BookReflection.create(user_id=user_id_vo, book_id=book_id_vo)
        return reflection
