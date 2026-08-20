"""
Use case for highlight upload operations.

Orchestrates highlight upload using domain entities and repositories.
No Pydantic dependencies - works with domain entities only.
"""

from dataclasses import dataclass

import structlog

from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.library.protocols.position_index_service import PositionIndexServiceProtocol
from src.application.reading.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.reading.protocols.highlight_repository import (
    DeviceEdit,
    HighlightRepositoryProtocol,
)
from src.application.reading.protocols.highlight_style_repository import (
    HighlightStyleRepositoryProtocol,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_enqueuer import EmbeddingEnqueuerProtocol
from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    ContentHash,
    HighlightId,
    UserId,
    XPointRange,
)
from src.domain.common.value_objects.position import Position
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.exceptions import BookNotFoundError
from src.domain.reading.services.deduplication_service import HighlightDeduplicationService

logger = structlog.get_logger(__name__)


@dataclass
class HighlightUploadData:
    """
    Simple data class for passing highlight data from API layer to use case layer.
    """

    text: str
    chapter_number: int | None = None
    chapter: str | None = None  # Chapter name (for warning logs)
    start_xpoint: str | None = None
    end_xpoint: str | None = None
    page: int | None = None
    color: str | None = None
    drawer: str | None = None
    datetime: str | None = None
    datetime_updated: str | None = None
    koreader_note: str | None = None


class HighlightUploadUseCase:
    """Use case for highlight upload operations."""

    def __init__(
        self,
        highlight_repository: HighlightRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
        deduplication_service: HighlightDeduplicationService,
        position_index_service: PositionIndexServiceProtocol,
        file_repository: FileRepositoryProtocol,
        highlight_style_repository: HighlightStyleRepositoryProtocol,
        embedding_enqueuer: EmbeddingEnqueuerProtocol,
    ) -> None:
        """
        Initialize use case with dependencies.

        Args:
            highlight_repository: Repository for highlight persistence
            book_repository: Repository for book lookup
            chapter_repository: Repository for chapter lookup
            deduplication_service: Domain service for deduplication logic
            position_index_service: Service for building position indices from EPUBs
            file_repository: Repository for file operations
            highlight_style_repository: Repository for highlight style persistence
            embedding_enqueuer: Seam for enqueuing embedding jobs for new highlights
        """
        self.highlight_repository = highlight_repository
        self.book_repository = book_repository
        self.chapter_repository = chapter_repository
        self.deduplication_service = deduplication_service
        self.position_index_service = position_index_service
        self.file_repository = file_repository
        self.highlight_style_repository = highlight_style_repository
        self._embedding_enqueuer = embedding_enqueuer

    async def upload_highlights(
        self,
        client_book_id: str,
        highlight_data_list: list[HighlightUploadData],
        user_id: int,
        device_id: str | None = None,
    ) -> tuple[int, int]:
        """
        Process highlight upload from KOReader.

        This method:
        1. Looks up the existing book by client_book_id
        2. Batch fetches chapters by chapter_number
        3. Creates domain entities using factory methods
        4. Deduplicates using domain service
        5. Applies the e-reader's newer note and style edits to skipped duplicates
        6. Fills in the xpoints and position of duplicates stored without them
        7. Bulk saves unique highlights

        Args:
            client_book_id: Book identifier from client
            highlight_data_list: List of highlight data to upload
            user_id: User ID (primitive int, converted to value object)
            device_id: Device the whole batch comes from, stamped on every highlight created

        Returns:
            Tuple of (created_count, skipped_count)

        Raises:
            BookNotFoundError: If book doesn't exist
        """
        logger.info(
            "processing_highlight_upload",
            book_client_id=client_book_id,
            highlight_count=len(highlight_data_list),
        )

        user_id_vo = UserId(user_id)
        book = await self.book_repository.find_by_client_book_id(client_book_id, user_id_vo)

        if not book:
            logger.error(
                "book_not_found_for_highlight_upload",
                client_book_id=client_book_id,
            )
            raise BookNotFoundError(client_book_id)

        book_id = book.id

        # Build position index if EPUB
        position_index = None
        if book.file_type == "epub" and book.ebook_file:
            epub_content = await self.file_repository.get_epub(book.ebook_file)
            if epub_content:
                position_index = self.position_index_service.build_position_index(epub_content)

        # Step 2: Batch fetch chapters by chapter_number
        chapter_numbers: set[int] = {
            data.chapter_number for data in highlight_data_list if data.chapter_number is not None
        }
        chapters_by_number = await self.chapter_repository.get_by_numbers(
            book.id, chapter_numbers, user_id_vo
        )

        # Step 3: Create domain entities using factory methods
        new_highlights: list[Highlight] = []

        for data in highlight_data_list:
            # Resolve chapter ID
            chapter_id: ChapterId | None = None
            if data.chapter_number is not None:
                chapter = chapters_by_number.get(data.chapter_number)
                if chapter:
                    chapter_id = chapter.id
                else:
                    logger.warning(
                        "chapter_not_found_for_highlight",
                        chapter_number=data.chapter_number,
                        book_id=book.id.value,
                        message="Chapter referenced by highlight doesn't exist. Upload EPUB to create chapters.",
                    )
            elif data.chapter:
                # No chapter_number - can't reliably associate with duplicate names
                logger.warning(
                    "highlight_missing_chapter_number",
                    chapter_name=data.chapter,
                    book_id=book.id.value,
                    message="Highlight has no chapter_number. Cannot associate reliably with duplicate chapter names.",
                )

            xpoints: XPointRange | None = None
            if data.start_xpoint and data.end_xpoint:
                xpoints = XPointRange.parse(data.start_xpoint, data.end_xpoint)

            position: Position | None = None
            if position_index and data.start_xpoint:
                position = position_index.resolve(data.start_xpoint)

            highlight_style = await self.highlight_style_repository.find_or_create(
                user_id=user_id_vo,
                book_id=book_id,
                device_color=data.color,
                device_style=data.drawer,
            )

            highlight = Highlight.create(
                user_id=user_id_vo,
                book_id=book_id,
                text=data.text,
                chapter_id=chapter_id,
                xpoints=xpoints,
                page=data.page,
                position=position,
                highlight_style_id=highlight_style.id,
                datetime_str=data.datetime,
                koreader_updated_at=data.datetime_updated,
                koreader_note=data.koreader_note,
                origin_device_id=device_id,
            )
            new_highlights.append(highlight)

        # Step 4: Deduplication using domain service
        existing_hashes = await self.highlight_repository.get_existing_hashes(
            user_id_vo, book_id, [h.content_hash for h in new_highlights]
        )

        unique, duplicates = self.deduplication_service.find_duplicates(
            new_highlights, existing_hashes
        )

        # Steps 5-6: reconcile the live rows the duplicates matched, loaded once
        stored_duplicates = await self.highlight_repository.find_live_by_content_hashes(
            user_id_vo, book_id, [duplicate.content_hash for duplicate in duplicates]
        )
        await self._sync_device_edits_of_duplicates(duplicates, stored_duplicates, book_id)
        await self._fill_missing_positions_of_duplicates(duplicates, stored_duplicates, book_id)

        # Step 7: Bulk save unique highlights
        if unique:
            saved = await self.highlight_repository.bulk_save(unique)
            await self._embedding_enqueuer.enqueue_many(
                ContentType.HIGHLIGHT,
                [highlight.id.value for highlight in saved],
                user_id,
                reference_id=str(book_id.value),
            )

        logger.info(
            "upload_complete",
            book_id=book.id.value,
            book_title=book.title,
            highlights_created=len(unique),
            highlights_skipped=len(duplicates),
        )

        return len(unique), len(duplicates)

    async def _sync_device_edits_of_duplicates(
        self,
        duplicates: list[Highlight],
        stored: list[Highlight],
        book_id: BookId,
    ) -> int:
        """
        Carry the e-reader's note and style edits onto skipped duplicates.

        A note or highlighter changed on the device after its highlight was
        first uploaded arrives inside a duplicate, which deduplication
        otherwise drops whole. Two devices can edit the same highlight, so the
        newest edit wins, as it does in KOReader itself: the device's
        ``datetime_updated`` (its creation ``datetime`` until it is first
        edited) is compared against the one stored, and the incoming edit is
        applied only if it is strictly newer. Equal timestamps keep the
        server's copy. The strings are KOReader's "%Y-%m-%d %H:%M:%S", which
        orders correctly as text, so no parsing is needed. A stored highlight
        that has never received a device edit accepts the first one whatever
        its time: there is nothing to protect, and rows uploaded before notes
        were kept carry a server-side ``datetime`` that a device edit made
        before that upload would never beat.

        An applied edit takes the incoming note, an empty one clearing the
        stored note, and the incoming style — but only when the incoming
        highlight resolved to one at all; without a colour or drawer to
        resolve, the stored style stays. Soft-deleted highlights are absent
        from the stored rows, so matching one must neither revive nor edit it.

        Args:
            duplicates: Highlights skipped by deduplication
            stored: The live highlights those duplicates matched
            book_id: Book the upload belongs to

        Returns:
            Number of stored highlights the device's edits were applied to
        """
        incoming_by_hash = {duplicate.content_hash: duplicate for duplicate in duplicates}

        edits: list[DeviceEdit] = []
        for highlight in stored:
            incoming = incoming_by_hash.get(highlight.content_hash)
            if incoming is None:
                continue

            incoming_edited_at = incoming.koreader_updated_at or incoming.datetime
            if self._has_recorded_device_edit(highlight):
                stored_edited_at = highlight.koreader_updated_at or highlight.datetime
                if incoming_edited_at <= stored_edited_at:
                    continue

            edits.append(
                DeviceEdit(
                    highlight_id=highlight.id,
                    koreader_note=incoming.koreader_note or None,
                    highlight_style_id=incoming.highlight_style_id
                    if incoming.highlight_style_id is not None
                    else highlight.highlight_style_id,
                    koreader_updated_at=incoming_edited_at,
                )
            )

        applied = await self.highlight_repository.bulk_apply_device_edits(edits)

        if applied:
            logger.info("highlight_device_edits_applied", book_id=book_id.value, count=applied)

        return applied

    @staticmethod
    def _has_recorded_device_edit(highlight: Highlight) -> bool:
        return highlight.koreader_updated_at is not None or highlight.koreader_note is not None

    async def _fill_missing_positions_of_duplicates(
        self,
        duplicates: list[Highlight],
        stored: list[Highlight],
        book_id: BookId,
    ) -> int:
        """
        Give skipped duplicates the xpoints and position their stored row lacks.

        Highlights uploaded before the e-reader sent xpoints are stored without
        them, and so cannot be placed in the book. A later upload carries the
        xpoints, but deduplication drops it whole, leaving the stored row
        unplaceable forever. Only the gap is filled: xpoints already stored
        stay, because the e-reader may re-anchor a highlight the reader never
        moved. The position comes with the incoming xpoints, already resolved
        against this book's EPUB, and stays NULL when there is no EPUB to
        resolve against. Soft-deleted highlights are absent from the stored
        rows and thus left untouched.

        Args:
            duplicates: Highlights skipped by deduplication
            stored: The live highlights those duplicates matched
            book_id: Book the upload belongs to

        Returns:
            Number of stored highlights given xpoints
        """
        incoming: dict[ContentHash, tuple[XPointRange, Position | None]] = {}
        for duplicate in duplicates:
            if duplicate.xpoints is not None:
                incoming[duplicate.content_hash] = (duplicate.xpoints, duplicate.position)

        placements: list[tuple[HighlightId, XPointRange, Position | None]] = []
        for highlight in stored:
            placement = incoming.get(highlight.content_hash)
            if placement is None or highlight.xpoints is not None:
                continue
            xpoints, position = placement
            placements.append((highlight.id, xpoints, highlight.position or position))

        filled = await self.highlight_repository.bulk_fill_xpoints_and_positions(placements)

        if filled:
            logger.info("highlight_positions_backfilled", book_id=book_id.value, count=filled)

        return filled
