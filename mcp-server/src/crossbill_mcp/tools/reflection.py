"""Book reflection MCP tools."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from crossbill_mcp.client import CrossbillClient


def register_reflection_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register book reflection tools with the MCP server."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_book_reflection(book_id: int) -> str:
        """Get a book's reflection: its answers to the four reading questions.

        The four questions are fixed: what is the book about, what does it say,
        do I agree, and so what. Each answer is not text but a reference to the
        note holding that answer's markdown, or null while the question is
        unanswered - read the answers with get_note. The reflection also keeps
        note_ids, the term and concept notes linked to it. Every book has a
        reflection; an untouched one simply has nulls and no linked notes.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_book_reflection(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def update_book_reflection(
        book_id: int,
        what_is_it_about_note_id: int | None = None,
        what_does_it_say_note_id: int | None = None,
        do_i_agree_note_id: int | None = None,
        so_what_note_id: int | None = None,
        note_ids: list[int] | None = None,
    ) -> str:
        """Replace a book's reflection in full.

        Answers live in ordinary notes, so answering a question is two steps:
        write the answer with create_note (or update_note), then pass that
        note's ID here as the question's answer.

        This is a full replace, not a patch: every field is overwritten with
        what you send, so omitting an answer clears it and omitting note_ids
        clears every linked note. Call get_book_reflection first and resend
        everything you want to keep, with your changes applied on top.

        Args:
            book_id: The ID of the book
            what_is_it_about_note_id: ID of the note answering "what is it
                about" (default None, clearing that answer)
            what_does_it_say_note_id: ID of the note answering "what does it
                say" (default None, clearing that answer)
            do_i_agree_note_id: ID of the note answering "do I agree" (default
                None, clearing that answer)
            so_what_note_id: ID of the note answering "so what" (default None,
                clearing that answer)
            note_ids: Full new set of linked term and concept note IDs
        """
        result = await client.update_book_reflection(
            book_id,
            what_is_it_about_note_id=what_is_it_about_note_id,
            what_does_it_say_note_id=what_does_it_say_note_id,
            do_i_agree_note_id=do_i_agree_note_id,
            so_what_note_id=so_what_note_id,
            note_ids=note_ids or [],
        )
        return json.dumps(result, indent=2, default=str)
