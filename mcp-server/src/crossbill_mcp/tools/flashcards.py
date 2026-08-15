"""Flashcard-related MCP tools."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from crossbill_mcp.ai_gate import ai_gated_json
from crossbill_mcp.client import CrossbillClient


def register_flashcard_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register flashcard-related tools with the MCP server."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_flashcards(book_id: int) -> str:
        """Get all flashcards for a book with their associated highlights.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_flashcards(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def create_flashcard(
        book_id: int,
        question: str,
        answer: str,
        highlight_id: int | None = None,
        note_id: int | None = None,
        chapter_id: int | None = None,
    ) -> str:
        """Create a new flashcard for a book, optionally anchored to its source.

        A flashcard always belongs to a book, and can additionally be anchored
        to the highlight, note or chapter it came from. Give at most one of
        highlight_id, note_id and chapter_id; a card with none of them is filed
        under the book alone. When anchored to a note, the book must be one the
        note is linked to.

        Args:
            book_id: The ID of the book
            question: The flashcard question
            answer: The flashcard answer
            highlight_id: Optional highlight ID to link the flashcard to
            note_id: Optional note ID to link the flashcard to
            chapter_id: Optional chapter ID to link the flashcard to
        """
        if note_id is not None:
            result = await client.create_note_flashcard(
                note_id, question, answer, book_id
            )
        else:
            result = await client.create_flashcard(
                book_id, question, answer, highlight_id, chapter_id
            )
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def update_flashcard(
        flashcard_id: int,
        question: str | None = None,
        answer: str | None = None,
    ) -> str:
        """Update a flashcard's question and/or answer.

        Args:
            flashcard_id: The ID of the flashcard
            question: New question text (optional)
            answer: New answer text (optional)
        """
        result = await client.update_flashcard(flashcard_id, question, answer)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False))
    async def delete_flashcard(flashcard_id: int) -> str:
        """Delete a flashcard.

        Args:
            flashcard_id: The ID of the flashcard
        """
        result = await client.delete_flashcard(flashcard_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def suggest_flashcards_for_chapter(chapter_id: int) -> str:
        """Suggest flashcards drawn from a chapter's digest.

        Returns AI-generated question/answer pairs only - nothing is saved.
        Pass the ones worth keeping to create_flashcard. Requires the chapter
        to already have a digest, so run generate_chapter_digest first if it
        has none.

        Args:
            chapter_id: The ID of the chapter
        """
        return await ai_gated_json(
            client.get_chapter_flashcard_suggestions(chapter_id)
        )

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def suggest_flashcards_for_highlight(highlight_id: int) -> str:
        """Suggest flashcards drawn from a highlight's text.

        Returns AI-generated question/answer pairs only - nothing is saved.
        Pass the ones worth keeping to create_flashcard.

        Args:
            highlight_id: The ID of the highlight
        """
        return await ai_gated_json(
            client.get_highlight_flashcard_suggestions(highlight_id)
        )

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def suggest_flashcards_for_note(note_id: int) -> str:
        """Suggest flashcards drawn from a note and its linked highlights.

        Returns AI-generated question/answer pairs only - nothing is saved.
        Pass the ones worth keeping to create_flashcard.

        Args:
            note_id: The ID of the note
        """
        return await ai_gated_json(client.get_note_flashcard_suggestions(note_id))
