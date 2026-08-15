"""Note-related MCP tools."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from crossbill_mcp.client import CrossbillClient


def register_notes_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register note-related tools with the MCP server."""

    @server.tool()
    async def create_note(
        book_id: int,
        title: str,
        body: str = "",
        kind: str | None = None,
        chapter_ids: list[int] | None = None,
        highlight_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
    ) -> str:
        """Create a markdown note in a book, optionally linked to other content.

        Notes belong to a book and can additionally be linked to any number of
        that book's chapters and highlights, and to any of the user's tags.
        Returns the created note, including its new ID.

        Args:
            book_id: The ID of the book the note belongs to
            title: Note title (required, must not be blank)
            body: Note body in markdown (default empty)
            kind: Optional note kind: "character", "term", "concept", "gist",
                "reflection" or "other"
            chapter_ids: IDs of chapters to link the note to
            highlight_ids: IDs of highlights to link the note to
            tag_ids: IDs of tags to attach to the note
        """
        result = await client.create_note(
            book_id,
            title,
            body=body,
            kind=kind,
            chapter_ids=chapter_ids or [],
            highlight_ids=highlight_ids or [],
            tag_ids=tag_ids or [],
        )
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_note(note_id: int) -> str:
        """Get a single note with its linked chapters, highlights and tags.

        Returns the note's fields plus summaries of everything linked to it,
        including any flashcards generated from it.

        Args:
            note_id: The ID of the note
        """
        result = await client.get_note(note_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_book_notes(
        book_id: int,
        kind: str | None = None,
        chapter_id: int | None = None,
        highlight_id: int | None = None,
        tag_id: int | None = None,
    ) -> str:
        """List a book's notes, optionally narrowed by kind or by what they link to.

        Every filter given is applied, so passing several narrows the list
        further. Returns the matching notes with their links.

        Args:
            book_id: The ID of the book
            kind: Keep only notes of this kind: "character", "term", "concept",
                "gist", "reflection" or "other"
            chapter_id: Keep only notes linked to this chapter
            highlight_id: Keep only notes linked to this highlight
            tag_id: Keep only notes carrying this tag
        """
        result = await client.get_book_notes(
            book_id,
            kind=kind,
            chapter_id=chapter_id,
            highlight_id=highlight_id,
            tag_id=tag_id,
        )
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def update_note(
        note_id: int,
        title: str,
        body: str = "",
        kind: str | None = None,
        chapter_ids: list[int] | None = None,
        highlight_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
    ) -> str:
        """Replace a note's fields and links in full.

        This is a full replace, not a patch: every field and every link list is
        overwritten with what you send. Omitting body, kind or a link list
        blanks that field and clears those links. Call get_note first and resend
        everything you want to keep, with your changes applied on top.

        Args:
            note_id: The ID of the note to replace
            title: New note title (required, must not be blank)
            body: New note body in markdown (default empty, clearing the body)
            kind: New note kind: "character", "term", "concept", "gist",
                "reflection" or "other" (default None, clearing the kind)
            chapter_ids: Full new set of linked chapter IDs
            highlight_ids: Full new set of linked highlight IDs
            tag_ids: Full new set of tag IDs
        """
        result = await client.update_note(
            note_id,
            title,
            body=body,
            kind=kind,
            chapter_ids=chapter_ids or [],
            highlight_ids=highlight_ids or [],
            tag_ids=tag_ids or [],
        )
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False))
    async def delete_note(note_id: int) -> str:
        """Delete a note and its links to chapters, highlights and tags.

        Args:
            note_id: The ID of the note to delete
        """
        result = await client.delete_note(note_id)
        return json.dumps(result, indent=2, default=str)
