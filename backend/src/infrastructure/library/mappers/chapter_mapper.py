from src.domain.common.value_objects.ids import BookId, ChapterId
from src.domain.common.value_objects.position import Position
from src.domain.library.entities.chapter import Chapter
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM


class ChapterMapper:
    """Mapper for Chapter ORM ↔ Domain conversion."""

    def to_domain(self, orm_model: ChapterORM) -> Chapter:
        """Convert ORM model to domain entity."""
        start_position = (
            Position.from_json(orm_model.start_position) if orm_model.start_position else None
        )
        end_position = (
            Position.from_json(orm_model.end_position) if orm_model.end_position else None
        )

        return Chapter.create_with_id(
            id=ChapterId(orm_model.id),
            book_id=BookId(orm_model.book_id),
            name=orm_model.name,
            created_at=orm_model.created_at,
            chapter_number=orm_model.chapter_number,
            parent_id=ChapterId(orm_model.parent_id) if orm_model.parent_id else None,
            start_xpoint=orm_model.start_xpoint,
            end_xpoint=orm_model.end_xpoint,
            start_position=start_position,
            end_position=end_position,
            start_offset=orm_model.start_offset,
        )

    def to_orm(self, domain_entity: Chapter, orm_model: ChapterORM | None = None) -> ChapterORM:
        """Convert domain entity to ORM model."""
        if orm_model is None:
            orm_model = ChapterORM(
                id=orm_id(domain_entity.id),
                created_at=domain_entity.created_at,
            )
        orm_model.book_id = domain_entity.book_id.value
        orm_model.parent_id = domain_entity.parent_id.value if domain_entity.parent_id else None
        orm_model.name = domain_entity.name
        orm_model.chapter_number = domain_entity.chapter_number
        orm_model.start_xpoint = domain_entity.start_xpoint
        orm_model.end_xpoint = domain_entity.end_xpoint
        orm_model.start_position = (
            domain_entity.start_position.to_json() if domain_entity.start_position else None
        )
        orm_model.end_position = (
            domain_entity.end_position.to_json() if domain_entity.end_position else None
        )
        orm_model.start_offset = domain_entity.start_offset
        return orm_model
