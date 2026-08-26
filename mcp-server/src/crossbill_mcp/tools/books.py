"""Book-related MCP tools."""

import json

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations

from crossbill_mcp.client import CrossbillClient
from crossbill_mcp.confirm import (
    REQUIRES_USER_INTERACTION,
    block_unconfirmed_deletion,
)


def register_book_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register book-related tools with the MCP server."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
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

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_book(book_id: int) -> str:
        """Get detailed information about a book including chapters and highlights.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_book(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
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

        The stage is one of "to_read", "skimming", "reading", "finished",
        "reflected" or "did_not_finish" for a book the user put down rather
        than completed. Omitting the stage clears the manual setting, leaving
        the book with no stage at all.

        Args:
            book_id: The ID of the book
            reading_stage: "to_read", "skimming", "reading", "finished",
                "reflected" or "did_not_finish"; omit to clear the stage
        """
        await client.set_reading_stage(book_id, reading_stage=reading_stage)
        if reading_stage is None:
            return f"Cleared the manual reading stage of book {book_id}."
        return f"Set the reading stage of book {book_id} to {reading_stage}."

    @server.tool(
        annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False),
        meta=REQUIRES_USER_INTERACTION,
    )
    async def delete_book(book_id: int, ctx: Context[ServerSession, None]) -> str:
        """Delete a book with all of its chapters and highlights.

        The user is asked to confirm before anything is deleted, and nothing is
        deleted if they decline. Clients that cannot show a confirmation prompt
        are refused outright.

        This is a hard delete and cannot be undone. Syncing the book from
        KOReader again recreates it, but everything Crossbill added on top -
        notes, flashcards, tags, digests - is gone for good.

        Args:
            book_id: The ID of the book to delete
        """
        book = await client.get_book(book_id)
        title = book.get("title") or f"book {book_id}"
        chapters = book.get("chapters") or []
        highlights = sum(len(chapter.get("highlights") or []) for chapter in chapters)
        refusal = await block_unconfirmed_deletion(
            ctx,
            f'Delete the book "{title}", with its {len(chapters)} chapters and '
            f"{highlights} highlights? This permanently deletes the book, its "
            f"chapters and highlights, and cannot be undone.",
        )
        if refusal is not None:
            return refusal

        await client.delete_book(book_id)
        return f'Deleted the book "{title}" with its chapters and highlights.'
