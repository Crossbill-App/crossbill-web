"""Tag and tag group MCP tools."""

import json

from mcp.server.fastmcp import FastMCP

from crossbill_mcp.client import CrossbillClient


def register_tag_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register tag and tag group tools with the MCP server."""

    @server.tool()
    async def get_book_tags(book_id: int) -> str:
        """Get every tag of a book, with the tag group each one belongs to.

        Tags belong to a single book and can be attached to that book's
        highlights and notes. A tag group is an optional folder that gathers
        related tags; a tag outside every group has a null tag_group_id.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_book_tags(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def create_tag(book_id: int, name: str) -> str:
        """Create a tag in a book and return it, including its new ID.

        The new tag starts out in no tag group; use update_tag to put it in
        one. To tag a highlight, use tag_highlight instead - it creates the tag
        by name when the book has none by that name yet.

        Args:
            book_id: The ID of the book the tag belongs to
            name: Tag name (1-100 characters, must be unique within the book)
        """
        result = await client.create_tag(book_id, name)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def update_tag(
        book_id: int,
        tag_id: int,
        name: str | None = None,
        tag_group_id: int | None = None,
    ) -> str:
        """Rename a tag and/or move it into a tag group.

        Args:
            book_id: The ID of the book the tag belongs to
            tag_id: The ID of the tag to update
            name: New tag name (1-100 characters); omit to keep the current one
            tag_group_id: ID of the tag group to move the tag into; omit to
                take the tag out of whatever group it is in
        """
        result = await client.update_tag(
            book_id, tag_id, name=name, tag_group_id=tag_group_id
        )
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def delete_tag(book_id: int, tag_id: int) -> str:
        """Delete a tag from a book.

        This also removes the tag from every highlight it was attached to, so
        the highlights themselves survive but lose that tag.

        Args:
            book_id: The ID of the book the tag belongs to
            tag_id: The ID of the tag to delete
        """
        await client.delete_tag(book_id, tag_id)
        return f"Deleted tag {tag_id} from book {book_id}."

    @server.tool()
    async def create_or_rename_tag_group(
        book_id: int, name: str, tag_group_id: int | None = None
    ) -> str:
        """Create a tag group in a book, or rename an existing one.

        A tag group is a named folder for a book's tags. Passing a
        tag_group_id renames that group instead of creating a new one. Returns
        the group either way; put tags into it with update_tag.

        Args:
            book_id: The ID of the book the tag group belongs to
            name: Tag group name (1-100 characters)
            tag_group_id: ID of an existing group to rename; omit to create a
                new group
        """
        result = await client.create_or_rename_tag_group(
            book_id, name, tag_group_id=tag_group_id
        )
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def delete_tag_group(tag_group_id: int) -> str:
        """Delete a tag group, leaving the tags in it ungrouped.

        Args:
            tag_group_id: The ID of the tag group to delete
        """
        await client.delete_tag_group(tag_group_id)
        return f"Deleted tag group {tag_group_id}."
