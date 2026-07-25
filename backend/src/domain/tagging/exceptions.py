"""Tagging module domain exceptions."""

from src.domain.common.exceptions import (
    ConflictError,
    EntityNotFoundError,
)


class TagNotFoundError(EntityNotFoundError):
    """Raised when a tag cannot be found."""

    def __init__(self, tag_id: int) -> None:
        super().__init__("Tag", tag_id)


class DuplicateTagNameError(ConflictError):
    """Raised when attempting to create a tag with a duplicate name."""

    def __init__(self, tag_name: str) -> None:
        super().__init__(
            f"Tag '{tag_name}' already exists for this book",
            {"tag_name": tag_name},
        )


class TagGroupNotFoundError(EntityNotFoundError):
    """Raised when a tag group cannot be found."""

    def __init__(self, group_id: int) -> None:
        super().__init__("TagGroup", group_id)


class DuplicateTagGroupNameError(ConflictError):
    """Raised when attempting to create a tag group with a duplicate name."""

    def __init__(self, group_name: str) -> None:
        super().__init__(
            f"Tag group '{group_name}' already exists for this book",
            {"group_name": group_name},
        )
