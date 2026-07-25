"""Repository for Tag and TagGroup domain entities."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.common.value_objects.ids import (
    BookId,
    HighlightId,
    TagGroupId,
    TagId,
    UserId,
)
from src.domain.tagging.entities.tag import Tag
from src.domain.tagging.entities.tag_group import TagGroup
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.notes.orm.associations import note_tags
from src.infrastructure.reading.mappers.tag_group_mapper import (
    TagGroupMapper,
)
from src.infrastructure.reading.mappers.tag_mapper import TagMapper
from src.infrastructure.reading.orm.associations import highlight_tags
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.reading.orm.tag_group_model import TagGroup as TagGroupORM
from src.infrastructure.reading.orm.tag_model import Tag as TagORM


class TagRepository(BaseRepository[Tag, TagORM]):
    """Repository for Tag and TagGroup domain entities.

    Plain ``Tag`` CRUD (``find_by_id``, ``find_by_ids``, ``save``, ``delete``)
    is inherited from :class:`BaseRepository`; the TagGroup and tag-highlight
    association helpers below are bespoke.
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

    async def find_groups_by_book(self, book_id: BookId) -> list[TagGroup]:
        """
        Find all tag groups for a book.

        Args:
            book_id: The book ID

        Returns:
            List of tag group entities, ordered by name
        """
        stmt = (
            select(TagGroupORM)
            .where(TagGroupORM.book_id == book_id.value)
            .order_by(TagGroupORM.name)
        )
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()
        return [self.group_mapper.to_domain(orm) for orm in orm_models]

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

    async def check_group_exists(self, group_id: TagGroupId) -> bool:
        """
        Check if a tag group exists (regardless of book).

        Args:
            group_id: The group ID

        Returns:
            True if the group exists, False otherwise
        """
        stmt = select(TagGroupORM.id).where(TagGroupORM.id == group_id.value)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
