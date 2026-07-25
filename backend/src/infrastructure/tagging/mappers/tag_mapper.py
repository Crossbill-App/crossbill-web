"""Mapper for Tag ORM ↔ Domain conversion."""

from sqlalchemy import inspect

from src.domain.common.value_objects.ids import BookId, TagId, UserId
from src.domain.tagging.entities.tag import Tag
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM


class TagMapper:
    """Mapper for Tag ORM ↔ Domain conversion."""

    def to_domain(self, orm_model: TagORM) -> Tag:
        """Convert ORM model to domain entity."""
        # Get tag_group_id from ORM
        tag_group_id = orm_model.tag_group_id

        # Get group name from tag_group relationship if loaded (avoid lazy load in async)
        group_name = None
        insp = inspect(orm_model)
        if "tag_group" not in insp.unloaded and orm_model.tag_group:
            group_name = orm_model.tag_group.name

        return Tag.create_with_id(
            id=TagId(orm_model.id),
            user_id=UserId(orm_model.user_id),
            book_id=BookId(orm_model.book_id),
            name=orm_model.name,
            tag_group_id=tag_group_id,
            group_name=group_name,
        )

    def to_orm(self, domain_entity: Tag, orm_model: TagORM | None = None) -> TagORM:
        """Convert domain entity to ORM model."""
        if orm_model is None:
            orm_model = TagORM(
                id=orm_id(domain_entity.id),
            )
        orm_model.user_id = domain_entity.user_id.value
        orm_model.book_id = domain_entity.book_id.value
        orm_model.name = domain_entity.name
        orm_model.tag_group_id = domain_entity.tag_group_id
        return orm_model
