from dataclasses import dataclass

from src.domain.common.entity import Entity
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects.ids import BookId, TagGroupId


@dataclass
class TagGroup(Entity[TagGroupId]):
    """Tag group for organizing tags within a book."""

    id: TagGroupId
    book_id: BookId
    name: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValidationError("Tag group name cannot be empty")

    def rename(self, new_name: str) -> None:
        """Rename the tag group."""
        if not new_name or not new_name.strip():
            raise ValidationError("Tag group name cannot be empty")
        object.__setattr__(self, "name", new_name.strip())

    @classmethod
    def create(cls, book_id: BookId, name: str) -> "TagGroup":
        """Create a new tag group."""
        return cls(
            id=TagGroupId.generate(),
            book_id=book_id,
            name=name.strip(),
        )

    @classmethod
    def create_with_id(
        cls,
        id: TagGroupId,
        book_id: BookId,
        name: str,
    ) -> "TagGroup":
        """Reconstitute a tag group from persistence."""
        return cls(
            id=id,
            book_id=book_id,
            name=name,
        )
