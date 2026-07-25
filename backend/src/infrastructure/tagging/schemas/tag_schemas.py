"""Pydantic schemas for Tag API request/response validation."""

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """Schema for Tag response."""

    id: int
    book_id: int
    tag_group_id: int | None = None
    name: str = Field(..., min_length=1, max_length=100, description="Tag name")

    model_config = {"from_attributes": True}


class TagInBook(BaseModel):
    """Minimal tag schema for book responses."""

    id: int
    name: str
    tag_group_id: int | None = None

    model_config = {"from_attributes": True}


class TagCreateRequest(BaseModel):
    """Schema for creating a new tag."""

    name: str = Field(..., min_length=1, max_length=100, description="Tag name")


class TagAssociationRequest(BaseModel):
    """Schema for associating a tag with a highlight."""

    tag_id: int | None = Field(None, description="ID of existing tag to associate")
    name: str | None = Field(
        None, min_length=1, max_length=100, description="Name of tag to create/associate"
    )


class TagUpdateRequest(BaseModel):
    """Schema for updating an existing tag."""

    name: str | None = Field(None, min_length=1, max_length=100, description="Tag name")
    tag_group_id: int | None = Field(None, description="ID of tag group to associate with")


class TagGroup(BaseModel):
    """Schema for TagGroup response."""

    id: int
    book_id: int
    name: str = Field(..., min_length=1, max_length=100, description="Tag group name")

    model_config = {"from_attributes": True}


class TagGroupInBook(BaseModel):
    """Minimal tag group schema for book responses."""

    id: int
    name: str

    model_config = {"from_attributes": True}


class TagGroupCreateRequest(BaseModel):
    """Schema for creating or updating a tag group."""

    id: int | None = Field(None, description="ID of existing tag group to update (optional)")
    book_id: int = Field(..., description="ID of the book this tag group belongs to")
    name: str = Field(..., min_length=1, max_length=100, description="Tag group name")
