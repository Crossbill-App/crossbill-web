"""Book-related MCP tools."""

import json

from mcp.server.fastmcp import FastMCP

from crossbill_mcp.client import CrossbillClient


def register_book_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register book-related tools with the MCP server."""

    @server.tool()
    async def list_books(
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """List books in the library with optional search.

        Args:
            search: Search by title or author
            limit: Maximum number of books to return (default 100)
            offset: Pagination offset (default 0)
        """
        result = await client.list_books(search=search, limit=limit, offset=offset)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def get_book(book_id: int) -> str:
        """Get detailed information about a book including chapters and highlights.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_book(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def get_recently_viewed_books(limit: int = 10) -> str:
        """Get recently viewed books.

        Args:
            limit: Maximum number of books to return (default 10)
        """
        result = await client.get_recently_viewed_books(limit=limit)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def set_reading_stage(book_id: int, reading_stage: str | None = None) -> str:
        """Set how far along the user is with a book, as a manual stage.

        The stage is one of "to_read", "skimming", "reading", "finished" or
        "reflected". Omitting the stage clears the manual setting, so the book
        goes back to the stage Crossbill infers from reading activity.

        Args:
            book_id: The ID of the book
            reading_stage: "to_read", "skimming", "reading", "finished" or
                "reflected"; omit to clear the stage back to automatic
        """
        await client.set_reading_stage(book_id, reading_stage=reading_stage)
        if reading_stage is None:
            return f"Cleared the manual reading stage of book {book_id}."
        return f"Set the reading stage of book {book_id} to {reading_stage}."
