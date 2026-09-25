"""Use case for attaching an EPUB to a book."""

import asyncio
import logging
from dataclasses import dataclass, replace

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.library.protocols.cover_image_service import CoverImageServiceProtocol
from src.application.library.protocols.epub_parser import EpubParserProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.library.protocols.position_index_service import PositionIndexServiceProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.protocols.reading_session_repository import (
    ReadingSessionRepositoryProtocol,
)
from src.application.web_reader.commands.backfill_book_locators_use_case import (
    BackfillBookLocatorsUseCase,
)
from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.protocols.publication_repository import (
    PublicationRepositoryProtocol,
)
from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.common.value_objects.position_index import PositionIndex
from src.domain.library.entities.book import Book
from src.domain.library.entities.chapter import TocChapter
from src.domain.library.exceptions import InvalidEbookError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DerivedEpub:
    cover: tuple[bytes, str] | None
    position_index: PositionIndex
    toc_chapters: list[TocChapter]
    publication: ParsedPublication | None


class AttachEpubUseCase:
    """Store an EPUB on a book along with everything derived from it."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
        file_repository: FileRepositoryProtocol,
        epub_parser: EpubParserProtocol,
        cover_image_service: CoverImageServiceProtocol,
        position_index_service: PositionIndexServiceProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        session_repository: ReadingSessionRepositoryProtocol,
        publication_parser: PublicationParserProtocol,
        publication_repository: PublicationRepositoryProtocol,
        backfill_book_locators_use_case: BackfillBookLocatorsUseCase,
    ) -> None:
        self.book_repository = book_repository
        self.chapter_repository = chapter_repository
        self.file_repository = file_repository
        self.epub_parser = epub_parser
        self.cover_image_service = cover_image_service
        self.position_index_service = position_index_service
        self.highlight_repository = highlight_repository
        self.session_repository = session_repository
        self.publication_parser = publication_parser
        self.publication_repository = publication_repository
        self._backfill_book_locators_use_case = backfill_book_locators_use_case

    async def attach_epub(self, book: Book, content: bytes, user_id: UserId) -> Book:
        """Attach the EPUB to the book and return the saved book.

        Every parse the upload depends on runs before the first write, so an EPUB
        that fails one leaves nothing stored.
        """
        # Off the event loop: the parses drive zipfile and lxml over the whole
        # book several times, and one thread hop covers them all.
        derived = await asyncio.to_thread(
            self._derive, content, book.id, extract_cover=book.cover_file is None
        )

        epub_filename = book.set_file("epub")
        await self.file_repository.save_epub(epub_filename, content)
        if derived.cover is not None:
            processed_bytes, blurhash = derived.cover
            cover_filename = book.set_cover_file()
            book.set_cover_blurhash(blurhash)
            await self.file_repository.save_cover(cover_filename, processed_bytes)
        total = derived.position_index.total_elements
        if total > 0:
            book.update_end_position(Position(index=total, char_index=0))
        book = await self.book_repository.save(book)

        await self._store_publication(book.id, epub_filename, derived.publication)
        if derived.toc_chapters:
            await self.chapter_repository.sync_chapters_from_toc(
                book.id, user_id, derived.toc_chapters
            )
        await self._backfill_positions(book.id, user_id, derived.position_index)
        # The file is what a locator was derived against, so a new one restates
        # every locator of the book -- whether or not the publication index took.
        await self._backfill_book_locators_use_case.backfill_book_locators(
            book.id, user_id, content
        )
        return book

    def _derive(self, content: bytes, book_id: BookId, *, extract_cover: bool) -> _DerivedEpub:
        if not self.epub_parser.validate_epub(content):
            raise InvalidEbookError("EPUB structure validation failed", ebook_type="EPUB")

        cover = None
        if extract_cover:
            # A cover is decoration and the EPUB is the book: a corrupt cover image
            # (as in nested_toc.epub) would otherwise fail the whole upload in Pillow.
            try:
                cover_bytes = self.epub_parser.extract_cover(content)
                if cover_bytes:
                    cover = self.cover_image_service.process_cover(cover_bytes)
            except Exception:
                logger.exception("Failed to derive a cover for book %s", book_id.value)

        position_index = self.position_index_service.build_position_index(content)
        toc_chapters = [
            replace(
                chapter,
                start_position=(
                    position_index.resolve(chapter.start_xpoint) if chapter.start_xpoint else None
                ),
                end_position=(
                    position_index.resolve(chapter.end_xpoint) if chapter.end_xpoint else None
                ),
            )
            for chapter in self.epub_parser.parse_toc(content)
        ]

        # The web reader's index is a cache: a missing one is derived again by the
        # first read that needs it, so its failure must not fail the upload.
        try:
            publication = self.publication_parser.parse_publication(content)
        except Exception:
            logger.exception("Failed to derive a publication index for book %s", book_id.value)
            publication = None
        return _DerivedEpub(cover, position_index, toc_chapters, publication)

    async def _store_publication(
        self, book_id: BookId, file_name: str, publication: ParsedPublication | None
    ) -> None:
        """Store the web reader's index, or drop a stale one when there is none to store."""
        if publication is not None:
            try:
                await self.publication_repository.save(book_id, file_name, publication)
                return
            except Exception:
                logger.exception("Failed to store a publication index for book %s", book_id.value)
        await self.publication_repository.delete(book_id)

    async def _backfill_positions(
        self,
        book_id: BookId,
        user_id: UserId,
        position_index: PositionIndex,
    ) -> None:
        highlights = await self.highlight_repository.find_by_book_id(book_id, user_id)
        highlight_updates = []
        for h in highlights:
            if h.xpoints and h.xpoints.start:
                pos = position_index.resolve(h.xpoints.start.to_string())
                if pos:
                    highlight_updates.append((h.id, pos))
        if highlight_updates:
            await self.highlight_repository.bulk_update_positions(highlight_updates)

        sessions = await self.session_repository.find_by_book_id(
            book_id, user_id, limit=10000, offset=0
        )
        session_updates = []
        for s in sessions:
            if s.start_xpoint:
                start_pos = position_index.resolve(s.start_xpoint.start.to_string())
                end_pos = position_index.resolve(s.start_xpoint.end.to_string())
                if start_pos and end_pos:
                    session_updates.append((s.id, start_pos, end_pos))
        if session_updates:
            await self.session_repository.bulk_update_positions(session_updates)
