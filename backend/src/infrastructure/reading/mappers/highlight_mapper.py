"""
Mapper for converting between Highlight ORM models and domain entities.

Handles bidirectional conversion:
- ORM model → Domain entity (when loading from database)
- Domain entity → ORM model (when persisting to database)
"""

from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    HighlightId,
    HighlightStyleId,
    UserId,
    XPointRange,
)
from src.domain.common.value_objects.position import Position
from src.domain.reading.entities.highlight import Highlight
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM


class HighlightMapper:
    """Mapper for Highlight ORM ↔ Domain conversion."""

    def to_domain(self, orm_model: HighlightORM) -> Highlight:
        """
        Convert ORM model to domain entity.

        Used when loading highlights from database.

        Args:
            orm_model: SQLAlchemy Highlight model

        Returns:
            Highlight domain entity
        """
        # Parse XPointRange if both start and end exist
        xpoints = None
        if orm_model.start_xpoint and orm_model.end_xpoint:
            xpoints = XPointRange.parse(orm_model.start_xpoint, orm_model.end_xpoint)

        position = Position.from_json(orm_model.position) if orm_model.position else None

        # Convert to domain entity using reconstitution factory
        return Highlight.create_with_id(
            id=HighlightId(orm_model.id),
            user_id=UserId(orm_model.user_id),
            book_id=BookId(orm_model.book_id),
            text=orm_model.text,
            device_datetime=orm_model.datetime,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
            chapter_id=ChapterId(orm_model.chapter_id) if orm_model.chapter_id else None,
            xpoints=xpoints,
            page=orm_model.page,
            position=position,
            highlight_style_id=HighlightStyleId(orm_model.highlight_style_id)
            if orm_model.highlight_style_id
            else None,
            deleted_at=orm_model.deleted_at,
            removed_from_devices_at=orm_model.removed_from_devices_at,
            koreader_updated_at=orm_model.koreader_updated_at,
            koreader_note=orm_model.koreader_note,
            origin_device_id=orm_model.origin_device_id,
        )

    def to_orm(
        self, domain_entity: Highlight, orm_model: HighlightORM | None = None
    ) -> HighlightORM:
        """
        Convert domain entity to ORM model.

        Used when persisting highlights to database.

        Args:
            domain_entity: Highlight domain entity
            orm_model: Optional existing ORM model to update (for updates)

        Returns:
            SQLAlchemy Highlight model
        """
        # Extract xpoint strings if present
        start_xpoint = None
        end_xpoint = None
        if domain_entity.xpoints:
            start_xpoint = domain_entity.xpoints.start.to_string()
            end_xpoint = domain_entity.xpoints.end.to_string()

        # Update existing ORM model or create new one
        if orm_model is None:
            orm_model = HighlightORM(
                id=orm_id(domain_entity.id),
                datetime=domain_entity.datetime,
                created_at=domain_entity.created_at,
            )
        orm_model.user_id = domain_entity.user_id.value
        orm_model.book_id = domain_entity.book_id.value
        orm_model.chapter_id = domain_entity.chapter_id.value if domain_entity.chapter_id else None
        orm_model.text = domain_entity.text
        orm_model.content_hash = domain_entity.content_hash.value
        orm_model.page = domain_entity.page
        orm_model.start_xpoint = start_xpoint
        orm_model.end_xpoint = end_xpoint
        orm_model.position = domain_entity.position.to_json() if domain_entity.position else None
        orm_model.highlight_style_id = (
            domain_entity.highlight_style_id.value if domain_entity.highlight_style_id else None
        )
        orm_model.deleted_at = domain_entity.deleted_at
        orm_model.removed_from_devices_at = domain_entity.removed_from_devices_at
        orm_model.koreader_updated_at = domain_entity.koreader_updated_at
        orm_model.koreader_note = domain_entity.koreader_note
        orm_model.origin_device_id = domain_entity.origin_device_id
        return orm_model
