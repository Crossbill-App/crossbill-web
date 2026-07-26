"""Repository for Tag and TagGroup domain entities."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import (
    BookId,
    TagGroupId,
    UserId,
)
from src.domain.tagging.entities.tag import Tag
from src.domain.tagging.entities.tag_group import TagGroup
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.notes.orm.associations import note_tags
from src.infrastructure.reading.orm.associations import highlight_tags
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.tagging.mappers.tag_group_mapper import (
    TagGroupMapper,
)
from src.infrastructure.tagging.mappers.tag_mapper import TagMapper
from src.infrastructure.tagging.orm.tag_group_model import TagGroup as TagGroupORM
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM


class TagRepository(BaseRepository[Tag, TagORM]):
    """Repository for Tag and TagGroup domain entities.

    Plain ``Tag`` CRUD (``find_by_id``, ``find_by_ids``, ``save``, ``delete``)
    is inherited from :class:`BaseRepository`; the TagGroup helpers below are
    bespoke. Tag-to-highlight and tag-to-note associations are owned by the
    modules holding them, so those repositories manage the link rows.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.mapper = TagMapper()
        self.group_mapper = TagGroupMapper()
        super().__init__(db, TagORM, self.mapper)

    # Tag methods

    async def find_by_book_and_name(
        self, book_id: BookId, name: str, user_id: UserId
    ) -> Tag | None:
        """
        Find a tag by book, name, and user.

        Args:
            book_id: The book ID
            name: The tag name
            user_id: The user ID

        Returns:
            Tag entity if found, None otherwise
        """
        stmt = select(TagORM).where(
            TagORM.book_id == book_id.value,
            TagORM.name == name,
            TagORM.user_id == user_id.value,
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return self.mapper.to_domain(orm_model) if orm_model else None

    async def find_by_book(self, book_id: BookId, user_id: UserId) -> list[Tag]:
        """
        Get all tags for a book that are in active use.

        A tag is "in use" when it is linked to a non-deleted highlight or to a
        note. This filters out tags that only have soft-deleted highlights and
        no note association. Notes have no soft-delete: deleting a note cascades
        away its ``note_tags`` rows, so any surviving note association is active.

        Args:
            book_id: The book ID
            user_id: The user ID

        Returns:
            List of tag entities
        """
        has_active_highlight = (
            select(highlight_tags.c.tag_id)
            .join(HighlightORM, HighlightORM.id == highlight_tags.c.highlight_id)
            .where(
                highlight_tags.c.tag_id == TagORM.id,
                HighlightORM.deleted_at.is_(None),
            )
            .exists()
        )
        has_note = select(note_tags.c.tag_id).where(note_tags.c.tag_id == TagORM.id).exists()
        stmt = (
            select(TagORM)
            .where(
                TagORM.book_id == book_id.value,
                TagORM.user_id == user_id.value,
                or_(has_active_highlight, has_note),
            )
            .order_by(TagORM.name)
        )
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()
        return [self.mapper.to_domain(orm) for orm in orm_models]

    # Tag group methods

    async def find_group_by_id(self, group_id: TagGroupId, book_id: BookId) -> TagGroup | None:
        """
        Find a tag group by ID and book ID.

        Args:
            group_id: The group ID
            book_id: The book ID

        Returns:
            Group entity if found, None otherwise
        """
        stmt = select(TagGroupORM).where(
            TagGroupORM.id == group_id.value,
            TagGroupORM.book_id == book_id.value,
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return self.group_mapper.to_domain(orm_model) if orm_model else None

    async def find_group_by_name(self, book_id: BookId, name: str) -> TagGroup | None:
        """
        Find a tag group by book and name.

        Args:
            book_id: The book ID
            name: The group name

        Returns:
            Group entity if found, None otherwise
        """
        stmt = select(TagGroupORM).where(
            TagGroupORM.book_id == book_id.value,
            TagGroupORM.name == name,
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return self.group_mapper.to_domain(orm_model) if orm_model else None

    async def save_group(self, group: TagGroup) -> TagGroup:
        """
        Save a tag group entity.

        Args:
            group: The group entity to save

        Returns:
            Saved group entity with updated ID
        """
        if group.id.value == 0:
            # Create new
            orm_model = self.group_mapper.to_orm(group)
            self.db.add(orm_model)
            await self.db.commit()
            await self.db.refresh(orm_model)
            return self.group_mapper.to_domain(orm_model)
        # Update existing
        stmt = select(TagGroupORM).where(TagGroupORM.id == group.id.value)
        result = await self.db.execute(stmt)
        existing_orm = result.scalar_one()
        self.group_mapper.to_orm(group, existing_orm)
        await self.db.commit()
        await self.db.refresh(existing_orm)
        return self.group_mapper.to_domain(existing_orm)

    async def delete_group(self, group_id: TagGroupId) -> bool:
        """
        Delete a tag group.

        Args:
            group_id: The group ID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(select(TagGroupORM).where(TagGroupORM.id == group_id.value))
        group_orm = result.scalar_one_or_none()

        if not group_orm:
            return False

        await self.db.delete(group_orm)
        await self.db.commit()
        return True
