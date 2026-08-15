"""Semantic search MCP tools."""

import json

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from crossbill_mcp.client import CrossbillClient

SEMANTIC_DISABLED_MESSAGE = (
    "Semantic search is not enabled on this Crossbill server "
    "(no embedding provider configured)."
)


def register_semantic_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register semantic search tools with the MCP server."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def semantic_search(
        query: str, book_id: int | None = None, limit: int = 10
    ) -> str:
        """Search highlights, notes and chapter digests by meaning, not keywords.

        Ranks the user's embedded content by semantic similarity to the query, so
        it finds passages that express an idea even when they share no words with
        it. Results come back grouped by content type (highlights, notes, digests);
        every group is present even when empty, and each item carries a similarity
        score on one shared scale plus the identifiers needed to open the source
        content.

        Args:
            query: What to search for, in natural language (1-1000 characters)
            book_id: Optional book ID to restrict the search to a single book
            limit: Maximum items per content type, not overall (1-100, default 10)
        """
        try:
            result = await client.semantic_search(query, book_id=book_id, limit=limit)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                return SEMANTIC_DISABLED_MESSAGE
            raise
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def find_related(content_type: str, content_id: int, limit: int = 10) -> str:
        """Find content semantically similar to an existing note, highlight or digest.

        Use this to follow a thread from one item the user already has: it ranks
        their other embedded content by similarity to that anchor. Same response
        shape as semantic_search - grouped by content type, with the limit applied
        per group. The anchor never appears among its own results, and every group
        is empty when the anchor has not been indexed yet.

        Args:
            content_type: Kind of the anchor item: "note", "highlight" or "digest"
            content_id: The ID of the anchor item
            limit: Maximum items per content type, not overall (1-100, default 10)
        """
        try:
            result = await client.related_content(content_type, content_id, limit=limit)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                return SEMANTIC_DISABLED_MESSAGE
            raise
        return json.dumps(result, indent=2, default=str)
