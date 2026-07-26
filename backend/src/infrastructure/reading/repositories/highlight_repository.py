"""
Domain-centric repository for Highlight aggregate.

Returns domain entities instead of ORM models.
Uses HighlightMapper internally for conversions.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.domain.common.value_objects import (
    BookId,
    ContentHash,
    HighlightId,
    ReadingSessionId,
    TagId,
    UserId,
)
from src.domain.common.value_objects.position import Position
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.reading.entities.highlight import Highlight
from src.domain.tagging.entities.tag import Tag
from src.infrastructure.learning.mappers.flashcard_mapper import FlashcardMapper
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.reading.mappers.highlight_mapper import HighlightMapper
from src.infrastructure.reading.orm.associations import reading_session_highlights
from src.infrastructure.reading.orm.bookmark_model import Bookmark as BookmarkORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.tagging.mappers.tag_mapper import TagMapper
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM

logger = logging.getLogger(__name__)


class HighlightRepository:
    """Repository for Highlight persistence (domain-centric)."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            db: SQLAlchemy async database session
        """
        self.db = db
        self.mapper = HighlightMapper()
        self.tag_mapper = TagMapper()
        self.flashcard_mapper = FlashcardMapper()

    async def find_by_id(self, highlight_id: HighlightId, user_id: UserId) -> Highlight | None:
        """
        Load highlight by ID.

        Args:
            highlight_id: Highlight ID to find
            user_id: User ID for authorization check

        Returns:
            Highlight domain entity if found, None otherwise
        """
        stmt = (
            select(HighlightORM)
            .where(HighlightORM.id == highlight_id.value)
            .where(HighlightORM.user_id == user_id.value)
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()

        if not orm_model:
            return None

        return self.mapper.to_domain(orm_model)

    async def find_by_ids(self, highlight_ids: list[int], user_id: UserId) -> list[Highlight]:
        """Load highlights by ids, scoped to the user."""
        if not highlight_ids:
            return []
        stmt = (
            select(HighlightORM)
            .where(HighlightORM.id.in_(highlight_ids))
            .where(HighlightORM.user_id == user_id.value)
        )
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()
        return [self.mapper.to_domain(m) for m in orm_models]

    async def find_by_id_with_relations(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> tuple[Highlight, list[Flashcard], list[Tag]] | None:
        """
        Load highlight by ID with its flashcards and tags eagerly loaded.

        Args:
            highlight_id: Highlight ID to find
            user_id: User ID for authorization check

        Returns:
            Tuple of (Highlight, list[Flashcard], list[Tag]) if found, None otherwise
        """
        stmt = (
            select(HighlightORM)
            .options(
                joinedload(HighlightORM.flashcards),
                joinedload(HighlightORM.tags),
            )
            .where(HighlightORM.id == highlight_id.value)
            .where(HighlightORM.user_id == user_id.value)
        )
        result = await self.db.execute(stmt)
        orm_model = result.unique().scalar_one_or_none()

        if not orm_model:
            return None

        highlight = self.mapper.to_domain(orm_model)
        flashcards = [self.flashcard_mapper.to_domain(fc_orm) for fc_orm in orm_model.flashcards]
        tags = [self.tag_mapper.to_domain(tag_orm) for tag_orm in orm_model.tags]

        return highlight, flashcards, tags

    async def save(self, highlight: Highlight) -> Highlight:
        """
        Persist highlight to database.

        If highlight has placeholder ID (0), creates new record and returns with real ID.
        Otherwise updates existing record.

        Args:
            highlight: Highlight domain entity to save

        Returns:
            Highlight with updated ID from database
        """
        if highlight.id.value == 0:
            # Create new highlight
            orm_model = self.mapper.to_orm(highlight)
            self.db.add(orm_model)
            await self.db.commit()
            await self.db.refresh(orm_model)

            # Return domain entity with real ID
            return self.mapper.to_domain(orm_model)
        # Update existing highlight
        stmt = select(HighlightORM).where(HighlightORM.id == highlight.id.value)
        result = await self.db.execute(stmt)
        existing_orm = result.scalar_one()

        # Update ORM model using mapper
        self.mapper.to_orm(highlight, existing_orm)
        await self.db.commit()
        await self.db.refresh(existing_orm)

        return self.mapper.to_domain(existing_orm)

    async def get_existing_hashes(
        self, user_id: UserId, book_id: BookId, hashes: list[ContentHash]
    ) -> set[ContentHash]:
        """
        Check which content hashes already exist for a user.

        Efficient deduplication check using unique constraint index.
        Includes both active and soft-deleted highlights to prevent
        recreating highlights that were previously deleted by the user.

        Args:
            user_id: User to check for
            book_id: Book containing the highlight
            hashes: List of ContentHash value objects to check

        Returns:
            Set of ContentHash value objects that already exist (including soft-deleted)
        """
        if not hashes:
            return set()

        # Convert value objects to strings for query
        hash_strings = [h.value for h in hashes]

        stmt = (
            select(HighlightORM.content_hash)
            .where(HighlightORM.user_id == user_id.value)
            .where(HighlightORM.book_id == book_id.value)
            .where(HighlightORM.content_hash.in_(hash_strings))
            # Include soft-deleted highlights to prevent recreation
        )

        result = await self.db.execute(stmt)
        existing = result.scalars().all()

        # Convert back to value objects
        return {ContentHash(hash_str) for hash_str in existing}

    async def bulk_save(self, highlights: list[Highlight]) -> list[Highlight]:
        """
        Bulk save highlights efficiently.

        All highlights must have placeholder IDs (new highlights).

        Args:
            highlights: List of new Highlight domain entities

        Returns:
            List of highlights with updated IDs from database
        """
        if not highlights:
            return []

        # Convert all to ORM models
        orm_models = [self.mapper.to_orm(h) for h in highlights]

        # Bulk insert
        self.db.add_all(orm_models)
        await self.db.flush()
        await self.db.commit()

        # Refresh all ORM models to load database-generated attributes
        for orm in orm_models:
            await self.db.refresh(orm)

        # Convert back to domain entities with real IDs
        return [self.mapper.to_domain(orm) for orm in orm_models]

    async def bulk_update_positions(
        self,
        position_updates: list[tuple[HighlightId, Position]],
    ) -> int:
        """Bulk update positions for highlights."""
        if not position_updates:
            return 0

        for highlight_id, position in position_updates:
            await self.db.execute(
                update(HighlightORM)
                .where(HighlightORM.id == highlight_id.value)
                .values(position=position.to_json())
            )

        await self.db.commit()
        return len(position_updates)

    async def soft_delete_by_ids(
        self,
        highlight_ids: list[HighlightId],
        user_id: UserId,
        book_id: BookId,
    ) -> int:
        """
        Soft delete highlights by IDs with value objects.

        Cascades to delete bookmarks and flashcards.

        Args:
            highlight_ids: List of highlight IDs to soft delete
            user_id: User ID for authorization check
            book_id: Book ID for validation

        Returns:
            Number of highlights soft deleted
        """
        # Convert value objects to primitives for query
        highlight_id_values = [hid.value for hid in highlight_ids]

        # Subquery to get valid highlight IDs (belong to book/user, not already deleted)
        valid_highlight_ids_subquery = (
            select(HighlightORM.id)
            .where(
                HighlightORM.id.in_(highlight_id_values),
                HighlightORM.book_id == book_id.value,
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
            .scalar_subquery()
        )

        # Bulk delete all bookmarks for valid highlights
        stmt_delete_bookmarks = delete(BookmarkORM).where(
            BookmarkORM.highlight_id.in_(valid_highlight_ids_subquery)
        )
        result = await self.db.execute(stmt_delete_bookmarks)
        bookmarks_deleted = getattr(result, "rowcount", 0) or 0

        # Bulk delete all flashcards for valid highlights
        stmt_delete_flashcards = delete(FlashcardORM).where(
            FlashcardORM.highlight_id.in_(valid_highlight_ids_subquery)
        )
        result = await self.db.execute(stmt_delete_flashcards)
        flashcards_deleted = getattr(result, "rowcount", 0) or 0

        # Bulk soft delete all valid highlights in a single query
        stmt_soft_delete = (
            update(HighlightORM)
            .where(
                HighlightORM.id.in_(highlight_id_values),
                HighlightORM.book_id == book_id.value,
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC))
        )
        result = await self.db.execute(stmt_soft_delete)
        count = getattr(result, "rowcount", 0) or 0

        await self.db.commit()
        logger.info(
            f"Soft deleted {count} highlights, {bookmarks_deleted} associated bookmarks, "
            f"and {flashcards_deleted} associated flashcards for book_id={book_id.value}, user_id={user_id.value}"
        )
        return count

    async def find_by_book_id(self, book_id: BookId, user_id: UserId) -> list[Highlight]:
        """
        Get all non-deleted highlights for a book.

        Args:
            book_id: Book ID value object
            user_id: User ID value object

        Returns:
            List of Highlight domain entities
        """
        stmt = select(HighlightORM).where(
            HighlightORM.book_id == book_id.value,
            HighlightORM.user_id == user_id.value,
            HighlightORM.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        orms = result.scalars().all()
        return [self.mapper.to_domain(orm) for orm in orms]

    async def count_by_book(self, book_id: BookId, user_id: UserId) -> int:
        """
        Count all non-deleted highlights for a book.

        Args:
            book_id: Book ID value object
            user_id: User ID value object for authorization

        Returns:
            Count of non-deleted highlights
        """
        stmt = select(func.count(HighlightORM.id)).where(
            HighlightORM.book_id == book_id.value,
            HighlightORM.user_id == user_id.value,
            HighlightORM.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_highlights_by_session_ids(
        self,
        session_ids: list[ReadingSessionId],
        user_id: UserId,
    ) -> dict[ReadingSessionId, list[Highlight]]:
        """
        Get highlights grouped by reading session IDs.

        Queries the reading_session_highlights join table to find all highlights
        associated with the given sessions.

        Args:
            session_ids: List of reading session IDs to fetch highlights for
            user_id: User ID for authorization check

        Returns:
            Dictionary mapping session_id -> list of highlights
        """
        if not session_ids:
            return {}

        session_id_values = [sid.value for sid in session_ids]

        # Query join table + highlights
        stmt = (
            select(reading_session_highlights.c.reading_session_id, HighlightORM)
            .join(
                HighlightORM,
                reading_session_highlights.c.highlight_id == HighlightORM.id,
            )
            .where(
                reading_session_highlights.c.reading_session_id.in_(session_id_values),
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
        )

        result = await self.db.execute(stmt)
        results = result.all()

        # Group results by session_id
        grouped: dict[ReadingSessionId, list[Highlight]] = {sid: [] for sid in session_ids}

        for session_id_value, highlight_orm in results:
            session_id = ReadingSessionId(session_id_value)
            highlight = self.mapper.to_domain(highlight_orm)
            grouped[session_id].append(highlight)

        return grouped

    # Tag-Highlight association methods

    async def add_tag_to_highlight(
        self, highlight_id: HighlightId, tag_id: TagId, user_id: UserId
    ) -> bool:
        """
        Add a tag to a highlight (manages the many-to-many association).

        Args:
            highlight_id: The highlight ID
            tag_id: The tag ID
            user_id: The user ID for authorization check

        Returns:
            True if added, False if already associated or not found
        """
        # Verify ownership and get ORM models
        result = await self.db.execute(
            select(HighlightORM)
            .options(selectinload(HighlightORM.tags))
            .where(
                HighlightORM.id == highlight_id.value,
                HighlightORM.user_id == user_id.value,
            )
        )
        highlight_orm = result.scalar_one_or_none()

        result = await self.db.execute(
            select(TagORM).where(
                TagORM.id == tag_id.value,
                TagORM.user_id == user_id.value,
            )
        )
        tag_orm = result.scalar_one_or_none()

        if not highlight_orm or not tag_orm:
            return False

        # Add association if not already present
        if tag_orm not in highlight_orm.tags:
            highlight_orm.tags.append(tag_orm)
            await self.db.commit()
            return True

        return False

    async def remove_tag_from_highlight(
        self, highlight_id: HighlightId, tag_id: TagId, user_id: UserId
    ) -> bool:
        """
        Remove a tag from a highlight (removes the many-to-many association).

        Args:
            highlight_id: The highlight ID
            tag_id: The tag ID
            user_id: The user ID for authorization check

        Returns:
            True if removed, False if not found or not associated
        """
        # Verify ownership and get ORM models
        result = await self.db.execute(
            select(HighlightORM)
            .options(selectinload(HighlightORM.tags))
            .where(
                HighlightORM.id == highlight_id.value,
                HighlightORM.user_id == user_id.value,
            )
        )
        highlight_orm = result.scalar_one_or_none()

        result = await self.db.execute(
            select(TagORM).where(
                TagORM.id == tag_id.value,
                TagORM.user_id == user_id.value,
            )
        )
        tag_orm = result.scalar_one_or_none()

        if not highlight_orm or not tag_orm:
            return False

        # Remove association if present
        if tag_orm in highlight_orm.tags:
            highlight_orm.tags.remove(tag_orm)
            await self.db.commit()
            return True

        return False
