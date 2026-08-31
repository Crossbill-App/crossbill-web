"""Reading session and chapter content MCP tools."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from crossbill_mcp.client import CrossbillClient


def register_reading_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register reading session and chapter content tools."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_reading_sessions(
        book_id: int, limit: int = 30, offset: int = 0
    ) -> str:
        """Get reading sessions for a book.

        Args:
            book_id: The ID of the book
            limit: Maximum number of sessions to return (default 30)
            offset: Pagination offset (default 0)
        """
        result = await client.get_reading_sessions(book_id, limit=limit, offset=offset)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_chapter_content(chapter_id: int) -> str:
        """Get the full text content of a chapter from the EPUB file.

        Use this to read and analyze the actual book content.

        Args:
            chapter_id: The ID of the chapter
        """
        result = await client.get_chapter_content(chapter_id)
        return json.dumps(result, indent=2, default=str)
