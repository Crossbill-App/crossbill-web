"""
Tag entity for categorizing book content.
"""

from dataclasses import dataclass

from src.domain.common.entity import Entity
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import (
    BookId,
    TagGroupId,
    TagId,
    UserId,
)


@dataclass
class Tag(Entity[TagId]):
    """
    Tag for categorizing content within a book (highlights, notes).

    Business Rules:
    - Tag names are scoped per book per user
    - Tags can optionally belong to groups
    """

    id: TagId
    user_id: UserId
    book_id: BookId
    name: str
    tag_group_id: int | None = None
    group_name: str | None = None

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.name or not self.name.strip():
            raise DomainError("Tag name cannot be empty")

    def rename(self, new_name: str) -> None:
        """
        Rename this tag.

        Args:
            new_name: New tag name

        Raises:
            DomainError: If new name is empty
        """
        if not new_name or not new_name.strip():
            raise DomainError("Tag name cannot be empty")

        self.name = new_name.strip()

    def set_group(self, group_name: str | None) -> None:
        """Set or clear the group for this tag."""
        self.group_name = group_name.strip() if group_name else None

    def update_group(self, group_id: TagGroupId | None) -> None:
        """
        Update the tag's group association.

        Args:
            group_id: The group ID to associate with, or None to clear
        """
        self.tag_group_id = group_id.value if group_id else None

    def belongs_to_book(self, book_id: BookId) -> bool:
        """Check if this tag belongs to the specified book."""
        return self.book_id == book_id

    @classmethod
    def create(
        cls,
        user_id: UserId,
        book_id: BookId,
        name: str,
        tag_group_id: TagGroupId | None = None,
    ) -> "Tag":
        """
        Create a new tag.

        Args:
            user_id: ID of the user creating the tag
            book_id: ID of the book this tag belongs to
            name: Name of the tag
            tag_group_id: Optional group ID to associate with

        Returns:
            New Tag instance
        """
        return cls(
            id=TagId.generate(),
            user_id=user_id,
            book_id=book_id,
            name=name.strip(),
            tag_group_id=tag_group_id.value if tag_group_id else None,
        )

    @classmethod
    def create_with_id(
        cls,
        id: TagId,
        user_id: UserId,
        book_id: BookId,
        name: str,
        tag_group_id: int | None = None,
        group_name: str | None = None,
    ) -> "Tag":
        """
        Reconstitute a tag from persistence.

        Args:
            id: Existing tag ID
            user_id: ID of the user who owns the tag
            book_id: ID of the book this tag belongs to
            name: Name of the tag
            tag_group_id: Optional group ID
            group_name: Optional group name

        Returns:
            Reconstituted Tag instance
        """
        return cls(
            id=id,
            user_id=user_id,
            book_id=book_id,
            name=name,
            tag_group_id=tag_group_id,
            group_name=group_name,
        )
