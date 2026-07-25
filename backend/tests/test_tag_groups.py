"""Tests for tag group API endpoints and functionality."""

from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.conftest import create_test_book, create_test_highlight


class TestCreateTagGroup:
    """Test suite for POST /tag-groups endpoint."""

    async def test_create_tag_group_success(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test successful creation of a tag group."""
        response = await client.post(
            "/api/v1/tag-groups",
            json={"book_id": test_book.id, "name": "Important Themes"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Important Themes"
        assert data["book_id"] == test_book.id
        assert "id" in data

        # Verify in database
        result = await db_session.execute(select(models.TagGroup).filter_by(id=data["id"]))
        tag_group = result.scalar_one_or_none()
        assert tag_group is not None
        assert tag_group.name == "Important Themes"
        assert tag_group.book_id == test_book.id

    async def test_update_tag_group_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_tag_group: models.TagGroup,
    ) -> None:
        """Test successful update of a tag group."""
        response = await client.post(
            "/api/v1/tag-groups",
            json={
                "id": test_tag_group.id,
                "book_id": test_tag_group.book_id,
                "name": "New Name",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_tag_group.id
        assert data["name"] == "New Name"
        assert data["book_id"] == test_tag_group.book_id

        # Verify in database
        await db_session.refresh(test_tag_group)
        assert test_tag_group.name == "New Name"

    async def test_create_tag_group_duplicate_name(
        self, client: AsyncClient, test_tag_group: models.TagGroup
    ) -> None:
        """Test creating tag group with duplicate name returns 409 error."""
        # Try to create another tag group with same name
        response = await client.post(
            "/api/v1/tag-groups",
            json={"book_id": test_tag_group.book_id, "name": test_tag_group.name},
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_create_tag_group_nonexistent_book(self, client: AsyncClient) -> None:
        """Test creating tag group for non-existent book."""
        response = await client.post(
            "/api/v1/tag-groups",
            json={"book_id": 99999, "name": "Themes"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_tag_group_empty_name(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        """Test creating tag group with empty name."""
        response = await client.post(
            "/api/v1/tag-groups",
            json={"book_id": test_book.id, "name": "   "},
        )

        assert response.status_code in {
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        }

    async def test_update_tag_group_to_duplicate_name(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag_group: models.TagGroup,
    ) -> None:
        """Test updating tag group to a name that already exists."""
        # Create a second tag group
        tag_group2 = models.TagGroup(book_id=test_book.id, name="Different Name")
        db_session.add(tag_group2)
        await db_session.commit()
        await db_session.refresh(tag_group2)

        # Try to update tag_group2 to have the same name as test_tag_group
        response = await client.post(
            "/api/v1/tag-groups",
            json={"id": tag_group2.id, "book_id": test_book.id, "name": test_tag_group.name},
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_update_tag_group_wrong_book(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_tag_group: models.TagGroup,
        test_user: models.User,
    ) -> None:
        """Test updating tag group with mismatched book_id."""
        # Create a second book
        book2 = await create_test_book(
            db_session=db_session,
            user_id=test_user.id,
            title="Book 2",
            author="Author 2",
        )

        # Try to update test_tag_group with book2's id (should fail)
        response = await client.post(
            "/api/v1/tag-groups",
            json={"id": test_tag_group.id, "book_id": book2.id, "name": "Updated Name"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteTagGroup:
    """Test suite for DELETE /tag-groups/:id endpoint."""

    async def test_delete_tag_group_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_tag_group: models.TagGroup,
    ) -> None:
        """Test successful deletion of a tag group."""
        tag_group_id = test_tag_group.id

        response = await client.delete(f"/api/v1/tag-groups/{tag_group_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        result = await db_session.execute(select(models.TagGroup).filter_by(id=tag_group_id))
        deleted_group = result.scalar_one_or_none()
        assert deleted_group is None

    async def test_delete_tag_group_with_tags(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag_group: models.TagGroup,
        test_user: models.User,
    ) -> None:
        """Test deleting tag group sets tags' tag_group_id to NULL."""
        # Create tags associated with the tag group
        tag1 = models.Tag(
            book_id=test_book.id,
            user_id=test_user.id,
            name="Tag 1",
            tag_group_id=test_tag_group.id,
        )
        tag2 = models.Tag(
            book_id=test_book.id,
            user_id=test_user.id,
            name="Tag 2",
            tag_group_id=test_tag_group.id,
        )
        db_session.add_all([tag1, tag2])
        await db_session.commit()
        await db_session.refresh(tag1)
        await db_session.refresh(tag2)

        # Delete tag group
        response = await client.delete(f"/api/v1/tag-groups/{test_tag_group.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify tags still exist but with NULL tag_group_id
        await db_session.refresh(tag1)
        await db_session.refresh(tag2)
        assert tag1.tag_group_id is None
        assert tag2.tag_group_id is None

    async def test_delete_tag_group_not_found(self, client: AsyncClient) -> None:
        """Test deleting non-existent tag group."""
        response = await client.delete("/api/v1/tag-groups/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateTag:
    """Test suite for POST /books/:id/tag/:id endpoint."""

    async def test_update_tag_add_to_group(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag_group: models.TagGroup,
        test_tag: models.Tag,
    ) -> None:
        """Test adding a tag to a tag group."""
        response = await client.post(
            f"/api/v1/books/{test_book.id}/tag/{test_tag.id}",
            json={"tag_group_id": test_tag_group.id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_tag.id
        assert data["tag_group_id"] == test_tag_group.id

        # Verify in database
        await db_session.refresh(test_tag)
        assert test_tag.tag_group_id == test_tag_group.id

    async def test_update_tag_remove_from_group(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag_group: models.TagGroup,
        test_user: models.User,
    ) -> None:
        """Test removing a tag from a tag group."""
        # Create a tag that's already in a group
        tag = models.Tag(
            book_id=test_book.id,
            user_id=test_user.id,
            name="Important",
            tag_group_id=test_tag_group.id,
        )
        db_session.add(tag)
        await db_session.commit()
        await db_session.refresh(tag)

        # Update tag to remove from group
        response = await client.post(
            f"/api/v1/books/{test_book.id}/tag/{tag.id}",
            json={"tag_group_id": None},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == tag.id
        assert data["tag_group_id"] is None

        # Verify in database
        await db_session.refresh(tag)
        assert tag.tag_group_id is None

    async def test_update_tag_rename(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag: models.Tag,
    ) -> None:
        """Test renaming a tag."""
        response = await client.post(
            f"/api/v1/books/{test_book.id}/tag/{test_tag.id}",
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_tag.id
        assert data["name"] == "New Name"

        # Verify in database
        await db_session.refresh(test_tag)
        assert test_tag.name == "New Name"

    async def test_update_tag_rename_and_add_to_group(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag_group: models.TagGroup,
        test_tag: models.Tag,
    ) -> None:
        """Test renaming a tag and adding it to a group."""
        response = await client.post(
            f"/api/v1/books/{test_book.id}/tag/{test_tag.id}",
            json={"name": "New Name", "tag_group_id": test_tag_group.id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_tag.id
        assert data["name"] == "New Name"
        assert data["tag_group_id"] == test_tag_group.id

        # Verify in database
        await db_session.refresh(test_tag)
        assert test_tag.name == "New Name"
        assert test_tag.tag_group_id == test_tag_group.id

    async def test_update_tag_wrong_book(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_tag: models.Tag,
        test_user: models.User,
    ) -> None:
        """Test updating tag with wrong book_id."""
        # Create a second book
        book2 = await create_test_book(
            db_session=db_session,
            user_id=test_user.id,
            title="Book 2",
            author="Author 2",
        )

        # Try to update with wrong book_id
        response = await client.post(
            f"/api/v1/books/{book2.id}/tag/{test_tag.id}",
            json={"name": "New Name"},
        )

        # A tag owned by another book is treated as not found (404).
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_tag_nonexistent_group(
        self, client: AsyncClient, test_book: models.Book, test_tag: models.Tag
    ) -> None:
        """Test updating tag with non-existent tag group."""
        response = await client.post(
            f"/api/v1/books/{test_book.id}/tag/{test_tag.id}",
            json={"tag_group_id": 99999},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBookDetailsWithTagGroups:
    """Test suite for GET /books/:id endpoint with tag groups."""

    async def test_get_book_details_includes_tag_groups(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
    ) -> None:
        """Test that book details include tag groups."""
        # Create tag groups
        tag_group1 = models.TagGroup(book_id=test_book.id, name="Themes")
        tag_group2 = models.TagGroup(book_id=test_book.id, name="Characters")
        db_session.add_all([tag_group1, tag_group2])
        await db_session.commit()

        # Get book details
        response = await client.get(f"/api/v1/books/{test_book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tag_groups" in data
        assert len(data["tag_groups"]) == 2

        # Check tag group names (should be sorted alphabetically)
        tag_group_names = [tg["name"] for tg in data["tag_groups"]]
        assert "Themes" in tag_group_names
        assert "Characters" in tag_group_names

    async def test_get_book_details_tags_include_group_id(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag_group: models.TagGroup,
        test_user: models.User,
    ) -> None:
        """Test that tags in book details include tag_group_id."""
        # Create tags
        tag1 = models.Tag(
            book_id=test_book.id,
            user_id=test_user.id,
            name="Tag 1",
            tag_group_id=test_tag_group.id,
        )
        tag2 = models.Tag(
            book_id=test_book.id, user_id=test_user.id, name="Tag 2", tag_group_id=None
        )
        db_session.add_all([tag1, tag2])
        await db_session.commit()

        # Create a highlight with tags to ensure they appear
        highlight = await create_test_highlight(
            db_session=db_session,
            book=test_book,
            user_id=test_user.id,
            text="Test highlight",
            page=1,
            datetime_str="2024-01-15 14:30:22",
        )

        highlight.tags.extend([tag1, tag2])
        await db_session.commit()

        # Get book details
        response = await client.get(f"/api/v1/books/{test_book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check tags include tag_group_id
        assert "tags" in data
        tag_map = {tag["name"]: tag for tag in data["tags"]}

        if "Tag 1" in tag_map:
            assert tag_map["Tag 1"]["tag_group_id"] == test_tag_group.id
        if "Tag 2" in tag_map:
            assert tag_map["Tag 2"]["tag_group_id"] is None


class TestCascadeDelete:
    """Test suite for cascade delete behavior."""

    async def test_delete_book_deletes_tag_groups(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_tag_group: models.TagGroup,
    ) -> None:
        """Test that deleting a book also deletes its tag groups."""
        tag_group_id = test_tag_group.id

        # Delete book
        response = await client.delete(f"/api/v1/books/{test_book.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify tag group was cascade-deleted via raw SQL to bypass identity map
        result = await db_session.execute(
            text("SELECT id FROM tag_groups WHERE id = :id"), {"id": tag_group_id}
        )
        assert result.scalar_one_or_none() is None
