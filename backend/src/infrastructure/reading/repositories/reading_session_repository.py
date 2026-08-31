"""
Domain-centric repository for ReadingSession aggregate.

Returns domain entities instead of ORM models.
Uses ReadingSessionMapper internally for conversions.
"""

import logging

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.protocols.reading_session_repository import BulkCreateResult
from src.domain.common.value_objects import BookId, HighlightId, ReadingSessionId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.reading.entities.reading_session import ReadingSession
from src.infrastructure.reading.mappers.reading_session_mapper import ReadingSessionMapper
from src.infrastructure.reading.orm.associations import reading_session_highlights
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM

logger = logging.getLogger(__name__)


class ReadingSessionRepository:
    """Repository for ReadingSession persistence (domain-centric)."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize repository.

        Args:
            db: SQLAlchemy async database session
        """
        self.db = db
        self.mapper = ReadingSessionMapper()

    async def bulk_create(
        self, user_id: UserId, sessions: list[ReadingSession]
    ) -> BulkCreateResult:
        """
        Bulk create reading sessions with deduplication.

        Uses PostgreSQL ON CONFLICT DO NOTHING or SQLite INSERT OR IGNORE
        to skip sessions with duplicate content_hash.

        Args:
            user_id: User ID value object
            sessions: List of ReadingSession domain entities

        Returns:
            BulkCreateResult with created count and created domain entities
        """
        if not sessions:
            return BulkCreateResult(created_count=0, created_sessions=[])

        # Map content_hash -> session for later retrieval
        session_by_hash = {s.content_hash.value: s for s in sessions}

        values = [
            {
                "book_id": s.book_id.value,
                "user_id": user_id.value,
                "content_hash": s.content_hash.value,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "start_xpoint": s.start_xpoint.start.to_string() if s.start_xpoint else None,
                "end_xpoint": s.start_xpoint.end.to_string() if s.start_xpoint else None,
                "start_page": s.start_page,
                "end_page": s.end_page,
                "start_position": s.start_position.to_json() if s.start_position else None,
                "end_position": s.end_position.to_json() if s.end_position else None,
                "device_id": s.device_id,
            }
            for s in sessions
        ]

        dialect = self.db.bind.dialect.name

        if dialect == "postgresql":
            stmt = (
                insert(ReadingSessionORM)
                .values(values)
                .on_conflict_do_nothing(index_elements=["user_id", "content_hash"])
                .returning(ReadingSessionORM.id)
            )
            result = await self.db.execute(stmt)
            created_ids = [row[0] for row in result.fetchall()]

            # Fetch the created sessions and convert to domain
            if created_ids:
                result = await self.db.execute(
                    select(ReadingSessionORM).where(ReadingSessionORM.id.in_(created_ids))
                )
                created_orms = list(result.scalars().all())
                created_sessions = [self.mapper.to_domain(orm) for orm in created_orms]
            else:
                created_sessions = []

            await self.db.commit()
            return BulkCreateResult(
                created_count=len(created_ids), created_sessions=created_sessions
            )

        # SQLite - count before and after to determine how many were inserted
        result = await self.db.execute(
            select(func.count(ReadingSessionORM.id)).where(
                ReadingSessionORM.user_id == user_id.value
            )
        )
        count_before = result.scalar() or 0

        stmt = insert(ReadingSessionORM).values(values).prefix_with("OR IGNORE")
        await self.db.execute(stmt)

        result = await self.db.execute(
            select(func.count(ReadingSessionORM.id)).where(
                ReadingSessionORM.user_id == user_id.value
            )
        )
        count_after = result.scalar() or 0

        created_count = count_after - count_before

        # For SQLite, fetch created sessions by content_hash
        if created_count > 0:
            content_hashes = list(session_by_hash.keys())
            result = await self.db.execute(
                select(ReadingSessionORM).where(
                    ReadingSessionORM.user_id == user_id.value,
                    ReadingSessionORM.content_hash.in_(content_hashes),
                )
            )
            created_orms = list(result.scalars().all())
            created_sessions = [self.mapper.to_domain(orm) for orm in created_orms]
        else:
            created_sessions = []

        await self.db.commit()
        return BulkCreateResult(created_count=created_count, created_sessions=created_sessions)

    async def find_by_book_id(
        self, book_id: BookId, user_id: UserId, limit: int, offset: int
    ) -> list[ReadingSession]:
        """
        Get reading sessions for a book with pagination.

        Ordered by start_time DESC.
        Does NOT load highlights (application layer's responsibility).

        Args:
            book_id: Book ID value object
            user_id: User ID value object
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of ReadingSession domain entities
        """
        stmt = (
            select(ReadingSessionORM)
            .where(
                ReadingSessionORM.book_id == book_id.value,
                ReadingSessionORM.user_id == user_id.value,
            )
            .order_by(ReadingSessionORM.start_time.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        orms = result.scalars().all()
        return [self.mapper.to_domain(orm) for orm in orms]

    async def find_by_id(
        self, session_id: ReadingSessionId, user_id: UserId
    ) -> ReadingSession | None:
        """
        Load reading session by ID.

        Args:
            session_id: Session ID value object
            user_id: User ID for authorization check

        Returns:
            ReadingSession domain entity if found, None otherwise
        """
        stmt = select(ReadingSessionORM).where(
            ReadingSessionORM.id == session_id.value,
            ReadingSessionORM.user_id == user_id.value,
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()

        if not orm_model:
            return None

        return self.mapper.to_domain(orm_model)

    async def bulk_update_positions(
        self,
        position_updates: list[tuple[ReadingSessionId, Position, Position]],
    ) -> int:
        """Bulk update start/end positions for reading sessions."""
        if not position_updates:
            return 0

        for session_id, start_pos, end_pos in position_updates:
            await self.db.execute(
                update(ReadingSessionORM)
                .where(ReadingSessionORM.id == session_id.value)
                .values(
                    start_position=start_pos.to_json(),
                    end_position=end_pos.to_json(),
                )
            )

        await self.db.commit()
        return len(position_updates)

    async def link_highlights_to_sessions(
        self,
        session_highlight_pairs: list[tuple[ReadingSessionId, HighlightId]],
    ) -> int:
        """
        Bulk link highlights to reading sessions via join table.

        Args:
            session_highlight_pairs: List of (session_id, highlight_id) tuples to link

        Returns:
            Number of links created
        """
        if not session_highlight_pairs:
            return 0

        # Build list of dicts for bulk insert
        links_to_insert = [
            {
                "reading_session_id": session_id.value,
                "highlight_id": highlight_id.value,
            }
            for session_id, highlight_id in session_highlight_pairs
        ]

        # Bulk insert into join table
        await self.db.execute(reading_session_highlights.insert(), links_to_insert)
        await self.db.commit()

        return len(links_to_insert)
