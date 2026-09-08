"""Getting at the EPUB behind a book row, shared by the web reader's query adapters.

Every web reader view is served out of the book's stored EPUB rather than out of
Postgres, so each adapter starts the same way: one row that says whether the
caller may see this book and which file holds it, then the file itself, then the
reading of it on a worker thread. That opening is here -- as
:func:`load_stored_epub` and the :class:`PublicationQuery` base that calls it --
so the manifest, the resource endpoint and the position list cannot drift on who
may read what, or on what they are willing to do to the event loop.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
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


class PublicationQuery:
    """What a web reader query adapter is before it decides what it reads.

    All three of them -- the manifest, one resource, the position list -- are
    built the same way and open the same way, because none of them is answered
    from Postgres. The book row only says whether the caller may look and which
    file to look in; the answer is in the EPUB. Subclasses supply the reading
    and nothing else.
    """

    def __init__(
        self,
        db: AsyncSession,
        file_repository: FileRepositoryProtocol,
        publication_parser: PublicationParserProtocol,
    ) -> None:
        self.db = db
        self.file_repository = file_repository
        self.publication_parser = publication_parser

    async def _read_publication[T](
        self, book_id: BookId, user_id: UserId, read: Callable[[StoredEpub], T]
    ) -> T | None:
        """Load a user's stored EPUB and read something out of it, off the event loop.

        Parsing a publication and pulling bytes out of a zip are both blocking
        and both CPU-bound, and they are proportional to the book rather than to
        the request. These are plain GETs a reader issues on every open, so a
        large publication handled inline would stall every other request in the
        process for the duration -- hence the one hop to a worker thread, which
        is here so that no view can quietly skip it.

        Returns:
            Whatever ``read`` returns, or ``None`` when the user has no such book.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
        """
        stored = await load_stored_epub(self.db, self.file_repository, book_id, user_id)
        if stored is None:
            return None
        return await asyncio.to_thread(read, stored)
