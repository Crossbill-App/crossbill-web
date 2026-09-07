"""Getting at the EPUB behind a book row, shared by the web reader's query adapters.

Every web reader view is served out of the book's stored EPUB rather than out of
Postgres, so each adapter starts the same way: one row that says whether the
caller may see this book and which file holds it, then the file itself. That
opening is here so the manifest and the resource endpoint cannot drift on who
may read what.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.exceptions import EbookFileNotFoundError
from src.infrastructure.library.orm.book_model import Book as BookORM


@dataclass(frozen=True)
class StoredEpub:
    """A book's EPUB, with the little the book row itself contributes.

    Attributes:
        title: The library's title for the book, which stands in when the
            package document states none.
        file_name: The name the EPUB is stored under. Part of a resource's
            entity tag, so that replacing a book's file invalidates every
            cached resource of it at once.
        content: The EPUB file's bytes.
    """

    title: str
    file_name: str
    content: bytes


async def load_stored_epub(
    db: AsyncSession,
    file_repository: FileRepositoryProtocol,
    book_id: BookId,
    user_id: UserId,
) -> StoredEpub | None:
    """Load the EPUB stored for a user's book.

    Returns:
        The stored EPUB, or ``None`` when the user has no such book.

    Raises:
        EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
    """
    stmt = select(BookORM.title, BookORM.ebook_file).where(
        BookORM.id == book_id.value,
        BookORM.user_id == user_id.value,
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None

    content = await file_repository.get_epub(row.ebook_file) if row.ebook_file else None
    if not content:
        raise EbookFileNotFoundError(book_id.value)
    return StoredEpub(title=row.title, file_name=row.ebook_file, content=content)
