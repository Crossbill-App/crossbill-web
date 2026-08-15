"""Chapter digest MCP tools."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from crossbill_mcp.ai_gate import ai_gated_json
from crossbill_mcp.client import CrossbillClient

NO_DIGEST_MESSAGE = (
    "No digest exists for this chapter yet. Use generate_chapter_digest to "
    "create one."
)

NO_ACTIVE_BATCH_MESSAGE = (
    "No active digest batch for this book. Use generate_book_digests to start "
    "one."
)


def register_digest_tools(server: FastMCP, client: CrossbillClient) -> None:
    """Register chapter digest tools with the MCP server."""

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_chapter_digest(chapter_id: int) -> str:
        """Get a chapter's digest: an AI-written study aid for that chapter.

        A digest holds a summary of the chapter, a list of keypoints, and
        comprehension questions with their answers and whatever the user has
        answered so far. Chapters only have one once it has been generated.

        Args:
            chapter_id: The ID of the chapter
        """
        result = await client.get_chapter_digest(chapter_id)
        if result is None:
            return NO_DIGEST_MESSAGE
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def generate_chapter_digest(chapter_id: int) -> str:
        """Generate the digest for one chapter and return it.

        This runs synchronously - it makes an AI call over the chapter text and
        can take tens of seconds. Overwrites any digest the chapter already
        has. To cover a whole book, use generate_book_digests instead, which
        runs in the background.

        Args:
            chapter_id: The ID of the chapter
        """
        return await ai_gated_json(client.generate_chapter_digest(chapter_id))

    @server.tool()
    async def answer_digest_question(
        chapter_id: int, question_index: int, user_answer: str
    ) -> str:
        """Record the user's answer to one comprehension question in a digest.

        Returns the updated digest, so the recorded answer can be compared with
        the digest's own answer for that question.

        Args:
            chapter_id: The ID of the chapter whose digest is being answered
            question_index: Zero-based index into the digest's questions list
            user_answer: The user's answer to that question
        """
        answers = [{"question_index": question_index, "user_answer": user_answer}]
        result = await client.update_digest_answers(chapter_id, answers)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_book_digests(book_id: int) -> str:
        """Get every chapter digest a book has.

        Chapters without a generated digest are simply absent from the list.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_book_digests(book_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool()
    async def generate_book_digests(book_id: int) -> str:
        """Enqueue digest generation for every chapter of a book.

        The work runs in the background, one job per chapter. Returns the job
        batch that was created; poll it with get_digest_generation_status to
        see how far along it is.

        Args:
            book_id: The ID of the book
        """
        return await ai_gated_json(client.enqueue_book_digests(book_id))

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_digest_generation_status(book_id: int) -> str:
        """Get the active digest generation batch for a book, if any.

        Returns the batch with its status and its total and completed job
        counts. Once the batch finishes it is no longer active, so use
        get_book_digests to read the results.

        Args:
            book_id: The ID of the book
        """
        result = await client.get_active_book_digest_batch(book_id)
        if result is None:
            return NO_ACTIVE_BATCH_MESSAGE
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_job_batch(batch_id: int) -> str:
        """Get any job batch by ID, with its status and progress counts.

        Args:
            batch_id: The ID of the job batch
        """
        result = await client.get_job_batch(batch_id)
        return json.dumps(result, indent=2, default=str)

    @server.tool(annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False))
    async def cancel_job_batch(batch_id: int) -> str:
        """Cancel a job batch, aborting the jobs in it that have not run yet.

        Jobs already finished keep their results. Returns the cancelled batch.

        Args:
            batch_id: The ID of the job batch
        """
        result = await client.cancel_job_batch(batch_id)
        return json.dumps(result, indent=2, default=str)
