"""Mapper for ReadingSession ORM ↔ Domain conversion."""

from src.domain.common.value_objects import (
    BookId,
    ReadingSessionId,
    UserId,
    XPointRange,
)
from src.domain.common.value_objects.position import Position
from src.domain.reading.entities.reading_session import ReadingSession
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM


class ReadingSessionMapper:
    """Mapper for ReadingSession ORM ↔ Domain conversion."""

    def to_domain(self, orm_model: ReadingSessionORM) -> ReadingSession:
        """
        Convert ORM model to domain entity.

        Uses constructor directly (NOT factory method) for reconstitution from database.
        Parses XPointRange if both start_xpoint and end_xpoint exist.
        """
        # Parse XPointRange if both xpoints exist
        xpoint_range = None
        if orm_model.start_xpoint and orm_model.end_xpoint:
            xpoint_range = XPointRange.parse(orm_model.start_xpoint, orm_model.end_xpoint)

        start_position = (
            Position.from_json(orm_model.start_position) if orm_model.start_position else None
        )
        end_position = (
            Position.from_json(orm_model.end_position) if orm_model.end_position else None
        )

        return ReadingSession(
            id=ReadingSessionId(orm_model.id),
            user_id=UserId(orm_model.user_id),
            book_id=BookId(orm_model.book_id),
            start_time=orm_model.start_time,
            end_time=orm_model.end_time,
            start_xpoint=xpoint_range,
            start_page=orm_model.start_page,
            end_page=orm_model.end_page,
            start_position=start_position,
            end_position=end_position,
            device_id=orm_model.device_id,
            created_at=orm_model.created_at,
        )

    def to_orm(
        self, domain_entity: ReadingSession, orm_model: ReadingSessionORM | None = None
    ) -> ReadingSessionORM:
        """
        Convert domain entity to ORM model.

        Handles both create (orm_model=None) and update (orm_model provided).
        Converts XPointRange to separate start_xpoint/end_xpoint strings.
        """
        # Extract XPointRange to separate strings
        start_xpoint_str = None
        end_xpoint_str = None
        if domain_entity.start_xpoint:
            start_xpoint_str = domain_entity.start_xpoint.start.to_string()
            end_xpoint_str = domain_entity.start_xpoint.end.to_string()

        if orm_model is None:
            orm_model = ReadingSessionORM(
                id=orm_id(domain_entity.id),
            )
        orm_model.user_id = domain_entity.user_id.value
        orm_model.book_id = domain_entity.book_id.value
        orm_model.start_time = domain_entity.start_time
        orm_model.end_time = domain_entity.end_time
        orm_model.content_hash = domain_entity.content_hash.value
        orm_model.start_xpoint = start_xpoint_str
        orm_model.end_xpoint = end_xpoint_str
        orm_model.start_page = domain_entity.start_page
        orm_model.end_page = domain_entity.end_page
        orm_model.start_position = (
            domain_entity.start_position.to_json() if domain_entity.start_position else None
        )
        orm_model.end_position = (
            domain_entity.end_position.to_json() if domain_entity.end_position else None
        )
        orm_model.device_id = domain_entity.device_id
        return orm_model
