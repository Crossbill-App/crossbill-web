"""Use case for ebook upload operations."""

import logging

from src.application.common.ownership import require_book_by_client_id
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
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.common.value_objects.position_index import PositionIndex
from src.domain.library.entities.book import Book
from src.domain.library.entities.chapter import TocChapter
from src.domain.library.exceptions import InvalidEbookError

logger = logging.getLogger(__name__)


class EbookUploadUseCase:
    """Use case for uploading ebook files."""

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
    ) -> None:
        """
        Initialize use case with dependencies.

        Args:
            book_repository: Book repository protocol implementation
            chapter_repository: Chapter repository protocol implementation
            file_repository: File repository protocol implementation
            epub_parser: EPUB parser service
            cover_image_service: Service for processing cover images
            position_index_service: Service for building position indices from EPUBs
            highlight_repository: Repository for highlight persistence
            session_repository: Repository for reading session persistence
        """
        self.book_repository = book_repository
        self.chapter_repository = chapter_repository
        self.file_repository = file_repository
        self.epub_parser = epub_parser
        self.cover_image_service = cover_image_service
        self.position_index_service = position_index_service
        self.highlight_repository = highlight_repository
        self.session_repository = session_repository

    async def upload_ebook(
        self,
        client_book_id: str,
        content: bytes,
        content_type: str,
        user_id: int,
    ) -> None:
        """
        Upload and save an ebook file (EPUB or PDF).

        Args:
            client_book_id: Client-provided book identifier
            content: File content as bytes
            content_type: MIME type of the file
            user_id: ID of the user uploading the file

        Raises:
            EntityNotFoundError: If book not found for the given client_book_id
            InvalidEbookError: If file validation fails
            NotImplementedError: If PDF upload is requested (not yet implemented)
        """
        # Route by content type
        if content_type in ["application/epub+zip", "application/epub"]:
            await self._upload_epub(client_book_id, content, UserId(user_id))
            return
        if content_type == "application/pdf":
            raise NotImplementedError("PDF upload not yet implemented")
        raise InvalidEbookError(f"Unsupported content type: {content_type}", ebook_type="UNKNOWN")

    async def _upload_epub(
        self,
        client_book_id: str,
        content: bytes,
        user_id: UserId,
    ) -> None:
        """
        Upload and validate an EPUB file for a book.

        This method:
        1. Validates the book exists and belongs to user
        2. Validates epub structure using ebooklib
        3. Saves file via file repository
        4. Updates book.ebook_file and book.file_type in database
        5. Parses TOC and saves chapters

        Args:
            client_book_id: Client-provided book identifier
            content: The epub file content as bytes
            user_id: ID of the user uploading the epub

        Raises:
            EntityNotFoundError: If book not found or doesn't belong to user
            InvalidEbookError: If epub structure validation fails
        """
        # Find book by client_book_id
        book = await require_book_by_client_id(self.book_repository, client_book_id, user_id)

        if not self.epub_parser.validate_epub(content):
            raise InvalidEbookError("EPUB structure validation failed", ebook_type="EPUB")

        # Get or generate UUID filename
        epub_filename = book.set_file("epub")
        await self.file_repository.save_epub(epub_filename, content)

        # Extract and save cover if none exists
        await self._extract_and_save_cover(book, content)

        # Build position index from EPUB DOM
        position_index = self.position_index_service.build_position_index(content)

        # Set end_position on book from total element count
        total = position_index.total_elements
        if total > 0:
            book.update_end_position(Position(index=total, char_index=0))

        await self.book_repository.save(book)

        # Parse TOC and sync chapters (with positions)
        toc_chapters = self.epub_parser.parse_toc(content)
        if toc_chapters:
            enriched_chapters = []
            for tc in toc_chapters:
                start_pos = position_index.resolve(tc.start_xpoint) if tc.start_xpoint else None
                end_pos = position_index.resolve(tc.end_xpoint) if tc.end_xpoint else None
                enriched_chapters.append(
                    TocChapter(
                        name=tc.name,
                        chapter_number=tc.chapter_number,
                        parent_name=tc.parent_name,
                        start_xpoint=tc.start_xpoint,
                        end_xpoint=tc.end_xpoint,
                        start_position=start_pos,
                        end_position=end_pos,
                    )
                )
            await self.chapter_repository.sync_chapters_from_toc(
                book.id, user_id, enriched_chapters
            )

        # Backfill positions for existing entities
        await self._backfill_positions(book.id, user_id, position_index)

    async def _extract_and_save_cover(
        self,
        book: Book,
        epub_content: bytes,
    ) -> None:
        """Extract cover from EPUB, resize, generate blurhash, and save."""
        if book.cover_file is not None:
            return

        cover_bytes = self.epub_parser.extract_cover(epub_content)
        if cover_bytes:
            processed_bytes, blurhash_str = self.cover_image_service.process_cover(cover_bytes)
            cover_filename = book.set_cover_file()
            book.set_cover_blurhash(blurhash_str)
            await self.file_repository.save_cover(cover_filename, processed_bytes)

    async def _backfill_positions(
        self,
        book_id: BookId,
        user_id: UserId,
        position_index: PositionIndex,
    ) -> None:
        """Backfill position data for existing highlights and reading sessions."""
        # Backfill highlights
        highlights = await self.highlight_repository.find_by_book_id(book_id, user_id)
        highlight_updates = []
        for h in highlights:
            if h.xpoints and h.xpoints.start:
                pos = position_index.resolve(h.xpoints.start.to_string())
                if pos:
                    highlight_updates.append((h.id, pos))
        if highlight_updates:
            await self.highlight_repository.bulk_update_positions(highlight_updates)

        # Backfill reading sessions
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
