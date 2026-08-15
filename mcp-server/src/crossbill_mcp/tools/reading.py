"""Reading session and chapter content MCP tools."""

import json

from mcp.server.fastmcp import FastMCP

from crossbill_mcp.ai_gate import ai_gated_json
from crossbill_mcp.client import CrossbillClient


def register_reading_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register reading session and chapter content tools."""

    @server.tool()
    async def get_reading_sessions(book_id: int, limit: int = 30) -> str:
        """Get reading sessions for a book.

        Args:
            book_id: The ID of the book
            limit: Maximum number of sessions to return (default 30)
        """
        result = await client.get_reading_sessions(book_id, limit=limit)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def get_chapter_content(chapter_id: int) -> str:
        """Get the full text content of a chapter from the EPUB file.

        Use this to read and analyze the actual book content.

        Args:
            chapter_id: The ID of the chapter
        """
        result = await client.get_chapter_content(chapter_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def get_reading_session_summary(reading_session_id: int) -> str:
        """Get an AI summary of what the user read in one reading session.

        The summary is written from the text covered between the session's
        start and end positions, and cached, so the AI call only happens the
        first time. Sessions without position data have nothing to summarise.
        Requires an AI provider configured on the Crossbill server.

        Args:
            reading_session_id: The ID of the reading session, from
                get_reading_sessions
        """
        return await ai_gated_json(
            client.get_reading_session_summary(reading_session_id)
        )
