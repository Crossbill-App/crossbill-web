"""The statement that reads a book's stored publication index."""

from sqlalchemy import Select, select

from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.web_reader.orm.book_publication_model import (
    BookPublication as BookPublicationORM,
)


def publication_row(book_id: BookId, user_id: UserId) -> Select[tuple[BookPublicationORM]]:
    """Select one book's index row, matching nothing when the book is someone else's.

    The ownership join is the access rule for every reader of this row, so it
    lives here rather than being restated at each of them.
    """
    return (
        select(BookPublicationORM)
        .join(BookORM, BookPublicationORM.book_id == BookORM.id)
        .where(BookPublicationORM.book_id == book_id.value)
        .where(BookORM.user_id == user_id.value)
    )
