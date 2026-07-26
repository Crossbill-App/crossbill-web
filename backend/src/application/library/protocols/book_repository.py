from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.entities.book import Book


class BookRepositoryProtocol(Protocol):
    async def find_by_client_book_id(self, client_book_id: str, user_id: UserId) -> Book | None: ...

    async def find_by_id(self, book_id: BookId, user_id: UserId) -> Book | None: ...

    async def save(self, book: Book) -> Book: ...

    async def delete(self, book: Book) -> None: ...
