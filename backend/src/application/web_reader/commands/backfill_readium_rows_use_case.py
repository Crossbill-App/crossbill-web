"""Derive the Readium rows of every book that already holds an EPUB, once."""

import asyncio
from dataclasses import dataclass

import structlog

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.commands.backfill_book_locators_use_case import (
    BackfillBookLocatorsUseCase,
)
from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.protocols.publication_repository import (
    PublicationRepositoryProtocol,
)
from src.domain.common.value_objects import BookId

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ReadiumBackfillReport:
    """What one run covered, for the single line its caller logs."""

    books_seen: int
    books_done: int
    epubs_missing: int
    books_failed: int


class BackfillReadiumRowsUseCase:
    """Give every book with an EPUB the publication index and locators an upload would."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        file_repository: FileRepositoryProtocol,
        publication_parser: PublicationParserProtocol,
        publication_repository: PublicationRepositoryProtocol,
        backfill_book_locators_use_case: BackfillBookLocatorsUseCase,
    ) -> None:
        self.book_repository = book_repository
        self.file_repository = file_repository
        self.publication_parser = publication_parser
        self.publication_repository = publication_repository
        self._backfill_book_locators_use_case = backfill_book_locators_use_case

    async def backfill_all(self) -> ReadiumBackfillReport:
        """Redo the derivation for every book of every user, overwriting what is stored.

        System-level on purpose: it fills a backlog nobody can trigger otherwise,
        because EPUBs only ever arrive from the KOReader plugin.
        """
        books = await self.book_repository.find_all_with_ebook_file()
        epubs_missing = 0
        books_failed = 0

        for book in books:
            file_name = book.ebook_file
            content = await self.file_repository.get_epub(file_name)
            # The listing already filters on the file name; naming it here as
            # well narrows it to ``str`` for the store below.
            if file_name is None or content is None:
                logger.warning(
                    "readium_backfill_epub_missing", book_id=book.id.value, file_name=file_name
                )
                epubs_missing += 1
                continue
            if not await self._store_publication(book.id, file_name, content):
                books_failed += 1
            await self._backfill_book_locators_use_case.backfill_book_locators(
                book.id, book.user_id, content
            )

        return ReadiumBackfillReport(
            books_seen=len(books),
            books_done=len(books) - epubs_missing - books_failed,
            epubs_missing=epubs_missing,
            books_failed=books_failed,
        )

    async def _store_publication(self, book_id: BookId, file_name: str, content: bytes) -> bool:
        # Unlike an upload, no new file has made a stored index stale, so a
        # failure here leaves whatever is there rather than deleting it.
        try:
            # Off the event loop: parsing drives zipfile and lxml over a whole book.
            publication = await asyncio.to_thread(
                self.publication_parser.parse_publication, content
            )
            await self.publication_repository.save(book_id, file_name, publication)
        except Exception:
            logger.exception("readium_backfill_publication_failed", book_id=book_id.value)
            return False
        return True
