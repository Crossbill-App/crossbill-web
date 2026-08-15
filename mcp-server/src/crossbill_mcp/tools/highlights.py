"""Highlight-related MCP tools."""

import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations

from crossbill_mcp.client import CrossbillClient
from crossbill_mcp.confirm import (
    REQUIRES_USER_INTERACTION,
    block_unconfirmed_deletion,
)


def register_highlight_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register highlight-related tools with the MCP server."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_highlights(book_id: int, search: str | None = None) -> str:
        """Get highlights from a book, optionally filtered by search text.

        If search is provided, uses full-text search to find matching highlights.
        If search is not provided, fetches the book with all highlights.

        Args:
            book_id: The ID of the book
            search: Optional search text to filter highlights
        """
        if search:
            result = await client.search_highlights(book_id, search)
        else:
            result = await client.get_book(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def update_highlight_note(highlight_id: int, note: str | None = None) -> str:
        """Add or update a note/annotation on a highlight.

        Args:
            highlight_id: The ID of the highlight
            note: The note text; omit it, or pass an empty string, to clear the
                highlight's note
        """
        result = await client.update_highlight_note(
            highlight_id, note if note else None
        )
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def tag_highlight(book_id: int, highlight_id: int, tag_name: str) -> str:
        """Add a tag to a highlight. Creates the tag if it doesn't exist.

        Args:
            book_id: The ID of the book
            highlight_id: The ID of the highlight
            tag_name: Name of the tag to add
        """
        result = await client.tag_highlight(book_id, highlight_id, tag_name)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def untag_highlight(book_id: int, highlight_id: int, tag_id: int) -> str:
        """Remove a tag from a highlight.

        Args:
            book_id: The ID of the book
            highlight_id: The ID of the highlight
            tag_id: The ID of the tag to remove
        """
        result = await client.untag_highlight(book_id, highlight_id, tag_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool(
        annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False),
        meta=REQUIRES_USER_INTERACTION,
    )
    async def delete_highlights(
        book_id: int, highlight_ids: list[int], ctx: Context[ServerSession, None]
    ) -> str:
        """Delete highlights from a book.

        The user is asked to confirm before anything is deleted, and nothing is
        deleted if they decline. Clients that cannot show a confirmation prompt
        are refused outright.

        The deletion sticks: a deleted highlight stays deleted, and future
        KOReader syncs of the book will not bring it back.

        Args:
            book_id: The ID of the book the highlights belong to
            highlight_ids: IDs of the highlights to delete (at least one)
        """
        if not highlight_ids:
            return "No highlight IDs given, so there is nothing to delete."

        book = await client.get_book(book_id)
        title = book.get("title") or f"book {book_id}"
        refusal = await block_unconfirmed_deletion(
            ctx,
            f'Delete {len(highlight_ids)} highlight(s) from "{title}"? Deleted '
            f"highlights stay deleted - future KOReader syncs of this book will "
            f"not bring them back.",
        )
        if refusal is not None:
            return refusal

        result = await client.delete_highlights(book_id, highlight_ids)
        return json.dumps(result, indent=2, default=str)
