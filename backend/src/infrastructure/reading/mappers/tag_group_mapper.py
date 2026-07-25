"""Mapper for TagGroup ORM ↔ Domain conversion."""

from src.domain.common.value_objects.ids import BookId, TagGroupId
from src.domain.tagging.entities.tag_group import TagGroup
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.reading.orm.tag_group_model import TagGroup as TagGroupORM


class TagGroupMapper:
    """Mapper for TagGroup ORM ↔ Domain conversion."""

    def to_domain(self, orm_model: TagGroupORM) -> TagGroup:
        """Convert ORM model to domain entity."""
        return TagGroup.create_with_id(
            id=TagGroupId(orm_model.id),
            book_id=BookId(orm_model.book_id),
            name=orm_model.name,
        )

    def to_orm(
        self,
        entity: TagGroup,
        orm_model: TagGroupORM | None = None,
    ) -> TagGroupORM:
        """Convert domain entity to ORM model."""
        if orm_model is None:
            orm_model = TagGroupORM(
                id=orm_id(entity.id),
                book_id=entity.book_id.value,
            )
        orm_model.name = entity.name
        return orm_model
