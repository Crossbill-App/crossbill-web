import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, ChapterId, UserId
from src.domain.library.entities.chapter import Chapter, TocChapter
from src.infrastructure.library.mappers.chapter_mapper import ChapterMapper
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM

logger = logging.getLogger(__name__)


class _ChapterTracker:
    """Tracks chapters by name and (name, parent_id) key during TOC sync."""

    def __init__(self, existing_chapters: Sequence[ChapterORM]) -> None:
        self._by_name: dict[str, ChapterORM] = {}
        self._by_key: dict[tuple[str, int | None], ChapterORM] = {}
        self._db_keys: set[tuple[str, int | None]] = set()
        for ch in existing_chapters:
            self._by_name[ch.name] = ch
            key = (ch.name, ch.parent_id)
            self._by_key[key] = ch
            self._db_keys.add(key)

    def resolve_parent_id(self, parent_name: str | None) -> int | None:
        """Look up the DB id for a parent chapter by name."""
        if parent_name is None:
            return None
        parent = self._by_name.get(parent_name)
        return parent.id if parent is not None else None

    def find_by_key(self, key: tuple[str, int | None]) -> ChapterORM | None:
        """Find a tracked chapter by its (name, parent_id) key."""
        return self._by_key.get(key)

    def is_from_db(self, key: tuple[str, int | None]) -> bool:
        """Return True if this key corresponds to a chapter loaded from the DB."""
        return key in self._db_keys

    def register_new(self, chapter: ChapterORM) -> None:
        """Register a newly created chapter for subsequent parent lookups."""
        self._by_name[chapter.name] = chapter
        self._by_key[(chapter.name, chapter.parent_id)] = chapter

    def rekey_legacy(
        self,
        chapter: ChapterORM,
        old_key: tuple[str, int | None],
        new_key: tuple[str, int | None],
    ) -> None:
        """Move a legacy chapter from old_key to new_key after migration."""
        del self._by_key[old_key]
        self._db_keys.discard(old_key)
        self._by_key[new_key] = chapter
        self._db_keys.add(new_key)
        self._by_name[chapter.name] = chapter


class ChapterRepository:
    """Domain-centric repository for Chapter persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.mapper = ChapterMapper()

    async def find_by_id(self, chapter_id: ChapterId, user_id: UserId) -> Chapter | None:
        """Find a chapter by ID with ownership verification."""
        stmt = (
            select(ChapterORM)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(ChapterORM.id == chapter_id.value)
            .where(BookORM.user_id == user_id.value)
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return self.mapper.to_domain(orm_model) if orm_model else None

    async def find_by_ids(self, chapter_ids: list[int], user_id: UserId) -> list[Chapter]:
        """Find chapters by ids with ownership verification (via the owning book)."""
        if not chapter_ids:
            return []
        stmt = (
            select(ChapterORM)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(ChapterORM.id.in_(chapter_ids))
            .where(BookORM.user_id == user_id.value)
        )
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()
        return [self.mapper.to_domain(m) for m in orm_models]

    async def find_all_by_book(self, book_id: BookId, user_id: UserId) -> list[Chapter]:
        """Find all chapters for a book, ordered by chapter_number."""
        stmt = (
            select(ChapterORM)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(BookORM.id == book_id.value)
            .where(BookORM.user_id == user_id.value)
            .order_by(ChapterORM.chapter_number)
        )
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()
        return [self.mapper.to_domain(m) for m in orm_models]

    async def get_by_numbers(
        self, book_id: BookId, chapter_numbers: set[int], user_id: UserId
    ) -> dict[int, Chapter]:
        """
        Get chapters by their numeric chapter_number.

        Returns dict mapping chapter_number -> Chapter entity.
        Only includes chapters with non-null chapter_number.
        Used during highlight upload for efficient chapter association.
        """
        if not chapter_numbers:
            return {}

        stmt = (
            select(ChapterORM)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(BookORM.id == book_id.value)
            .where(BookORM.user_id == user_id.value)
            .where(ChapterORM.chapter_number.in_(chapter_numbers))
            .where(ChapterORM.chapter_number.is_not(None))
        )

        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()

        # Map to dict by chapter_number
        result_dict: dict[int, Chapter] = {}
        for orm_model in orm_models:
            if orm_model.chapter_number is not None:
                result_dict[orm_model.chapter_number] = self.mapper.to_domain(orm_model)

        return result_dict

    @staticmethod
    def _apply_field_updates(orm: ChapterORM, toc: TocChapter, parent_id: int | None) -> bool:
        """Apply field values from TOC entry to existing ORM. Returns True if anything changed."""
        changed = False
        for attr, new_val in [
            ("chapter_number", toc.chapter_number),
            ("parent_id", parent_id),
            ("start_xpoint", toc.start_xpoint),
            ("end_xpoint", toc.end_xpoint),
            ("start_position", toc.start_position.to_json() if toc.start_position else None),
            ("end_position", toc.end_position.to_json() if toc.end_position else None),
        ]:
            if getattr(orm, attr) != new_val:
                setattr(orm, attr, new_val)
                changed = True
        return changed

    def _match_legacy_flat_chapter(self, name: str, tracker: _ChapterTracker) -> ChapterORM | None:
        """Match a TOC chapter to a legacy flat chapter (parent_id=None) by name.

        Before hierarchical TOC support was added, chapters were stored without
        parent associations. When an EPUB is uploaded for a book with such legacy
        chapters, we need to match them by name alone to avoid creating duplicates
        and to preserve existing highlight foreign key references.

        This is migration-era logic that can be removed once all production books
        have been re-uploaded with hierarchical TOC data.
        """
        legacy_key = (name, None)
        chapter = tracker.find_by_key(legacy_key)
        # If chapter does not have start point, it has to be legacy
        if chapter is not None and tracker.is_from_db(legacy_key) and chapter.start_xpoint is None:
            return chapter
        return None

    @staticmethod
    def _resolve_parent_id(
        ch: TocChapter,
        resolved: dict[int, ChapterORM],
        tracker: _ChapterTracker,
    ) -> int | None:
        """Resolve the DB id of a TOC entry's parent.

        `parent_index` points at a position in the TOC list being synced, and every
        processed entry records the row it resolved to, so the parent is exact even
        when several chapters share a name. Only callers that build TocChapter
        without indexes fall back to the ambiguous by-name lookup.
        """
        if ch.parent_index is None:
            return tracker.resolve_parent_id(ch.parent_name)
        parent = resolved.get(ch.parent_index)
        return parent.id if parent is not None else None

    async def _create_chapter_orm(
        self,
        book_id: BookId,
        ch: TocChapter,
        parent_id: int | None,
        tracker: _ChapterTracker,
    ) -> ChapterORM:
        """Create a new chapter ORM, persist it, and register in tracker."""
        chapter = ChapterORM(
            book_id=book_id.value,
            name=ch.name,
            chapter_number=ch.chapter_number,
            parent_id=parent_id,
            start_xpoint=ch.start_xpoint,
            end_xpoint=ch.end_xpoint,
            start_position=ch.start_position.to_json() if ch.start_position else None,
            end_position=ch.end_position.to_json() if ch.end_position else None,
        )
        self.db.add(chapter)
        await self.db.commit()
        await self.db.refresh(chapter)
        tracker.register_new(chapter)
        return chapter

    async def sync_chapters_from_toc(
        self,
        book_id: BookId,
        user_id: UserId,
        chapters: list[TocChapter],
    ) -> int:
        """
        Synchronize chapters from TOC data, creating new and updating existing chapters.

        This method handles bulk chapter creation/update from EPUB TOC parsing.
        It preserves hierarchical parent-child relationships and handles duplicates.

        Args:
            book_id: ID of the book
            user_id: ID of the user (for ownership verification)
            chapters: List of TocChapter objects from EPUB TOC parsing

        Returns:
            Number of chapters created (not including updates)
        """
        if not chapters:
            return 0

        # Stage 1: Fetch existing chapters and build index
        chapter_names = {ch.name for ch in chapters}
        stmt = (
            select(ChapterORM)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(BookORM.id == book_id.value)
            .where(BookORM.user_id == user_id.value)
            .where(ChapterORM.name.in_(chapter_names))
        )
        result = await self.db.execute(stmt)
        existing_chapters_list = result.scalars().all()
        tracker = _ChapterTracker(list(existing_chapters_list))

        updated: list[ChapterORM] = []
        created_count = 0

        # Stage 2: Process each TOC entry (sequential -- parents before children).
        # `resolved` maps a TOC entry's position to the row it resolved to, which is
        # what a child's parent_index refers to.
        resolved: dict[int, ChapterORM] = {}

        for index, ch in enumerate(chapters):
            parent_id = self._resolve_parent_id(ch, resolved, tracker)
            key = (ch.name, parent_id)
            existing_chapter = tracker.find_by_key(key)

            # Case 1: Exact match by (name, parent_id)
            if existing_chapter is not None:
                resolved[index] = existing_chapter
                if not tracker.is_from_db(key):
                    logger.warning(
                        f"Duplicate chapter '{ch.name}' in ToC with same parent "
                        f"(parent_id={parent_id}). Skipping duplicate."
                    )
                    continue
                if self._apply_field_updates(existing_chapter, ch, parent_id):
                    updated.append(existing_chapter)
                continue

            # Case 2: Legacy flat chapter migration
            legacy = (
                self._match_legacy_flat_chapter(ch.name, tracker) if parent_id is not None else None
            )
            if legacy is not None:
                self._apply_field_updates(legacy, ch, parent_id)
                updated.append(legacy)
                tracker.rekey_legacy(legacy, old_key=(ch.name, None), new_key=key)
                resolved[index] = legacy
                continue

            # Case 3: Truly new chapter
            resolved[index] = await self._create_chapter_orm(book_id, ch, parent_id, tracker)
            created_count += 1

        # Stage 3: Commit updates
        if updated:
            await self.db.commit()
            logger.info(f"Updated {len(updated)} existing chapters")

        logger.info(
            f"Synced TOC for book {book_id.value}: created {created_count} chapters, "
            f"updated {len(updated)} chapters"
        )
        return created_count
