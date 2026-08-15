"""Highlight label MCP tools."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from crossbill_mcp.client import CrossbillClient


def register_highlight_label_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register highlight-label tools with the MCP server."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_book_highlight_labels(book_id: int) -> str:
        """Get all highlight labels for a book with their resolved labels and highlight counts.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_book_highlight_labels(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_global_highlight_labels() -> str:
        """Get all global default highlight labels."""
        result = await client.get_global_highlight_labels()
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def update_highlight_label(
        style_id: int, label: str | None = None, ui_color: str | None = None
    ) -> str:
        """Update label text and/or UI color on a highlight style.

        Args:
            style_id: The ID of the highlight style to update
            label: New label text (pass empty string to clear)
            ui_color: New UI color (hex string, e.g. "#ff0000")
        """
        result = await client.update_highlight_label(style_id, label, ui_color)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def create_global_highlight_label(
        device_color: str | None = None,
        device_style: str | None = None,
        label: str | None = None,
        ui_color: str | None = None,
    ) -> str:
        """Create a new global default highlight label.

        Args:
            device_color: The device color identifier
            device_style: The device style identifier
            label: Label text for the highlight style
            ui_color: UI color (hex string, e.g. "#ff0000")
        """
        result = await client.create_global_highlight_label(
            device_color, device_style, label, ui_color
        )
        return json.dumps(result, indent=2, default=str)
