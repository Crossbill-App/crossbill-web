from collections.abc import Sequence
from datetime import UTC, datetime

import structlog
from pydantic_ai import Agent, ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_core import to_jsonable_python

from src.application.ai.ai_usage_context import AIUsageContext
from src.application.ai.protocols.ai_usage_repository import AIUsageRepositoryProtocol
from src.application.learning.protocols.ai_flashcard_service import AIFlashcardSuggestion
from src.application.reading.protocols.ai_digest_service import (
    DigestQuestion,
    DigestResult,
)
from src.domain.ai.entities.ai_usage_record import AIUsageRecord
from src.domain.common.types import SerializedMessageHistory
from src.infrastructure.ai.ai_agents import (
    get_chat_agent,
    get_digest_agent,
    get_flashcard_agent,
    get_quiz_agent,
    get_summary_agent,
)

logger = structlog.get_logger(__name__)

MAX_CHAPTER_CONTEXT_CHARS = 10000

#: The one ``AIUsageContext.entity_type`` whose ``entity_id`` names a chapter.
CHAPTER_ENTITY_TYPE = "chapter"


def chapter_id_of(usage_context: AIUsageContext) -> int:
    if usage_context.entity_type != CHAPTER_ENTITY_TYPE:
        raise ValueError(
            f"chapter content truncation needs a {CHAPTER_ENTITY_TYPE} usage context, "
            f"got {usage_context.entity_type!r}"
        )
    return usage_context.entity_id


def truncate_chapter_content(content: str, *, chapter_id: int) -> str:
    if len(content) <= MAX_CHAPTER_CONTEXT_CHARS:
        return content
    dropped_chars = len(content) - MAX_CHAPTER_CONTEXT_CHARS
    logger.info(
        "chapter_content_truncated",
        chapter_id=chapter_id,
        dropped_chars=dropped_chars,
    )
    return content[:MAX_CHAPTER_CONTEXT_CHARS]


class AIService:
    def __init__(self, usage_repository: AIUsageRepositoryProtocol) -> None:
        self.usage_repository = usage_repository

    async def _save_usage(
        self,
        usage_context: AIUsageContext,
        model_name: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        record = AIUsageRecord.create(
            user_id=usage_context.user_id,
            task_type=usage_context.task_type,
            entity_type=usage_context.entity_type,
            entity_id=usage_context.entity_id,
            model_name=model_name or "unknown",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            created_at=datetime.now(UTC),
        )
        await self.usage_repository.save(record)
        logger.info(
            "ai_usage_recorded",
            task_type=usage_context.task_type,
            entity_type=usage_context.entity_type,
            entity_id=usage_context.entity_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=model_name,
        )

    async def generate_summary(self, content: str, usage_context: AIUsageContext) -> str:
        agent = get_summary_agent()
        result = await agent.run(content)
        usage = result.usage()
        await self._save_usage(
            usage_context, result.response.model_name, usage.input_tokens, usage.output_tokens
        )
        return result.output

    async def generate_digest(self, content: str, usage_context: AIUsageContext) -> DigestResult:
        agent = get_digest_agent()
        content = truncate_chapter_content(content, chapter_id=chapter_id_of(usage_context))
        result = await agent.run(content)
        usage = result.usage()
        await self._save_usage(
            usage_context, result.response.model_name, usage.input_tokens, usage.output_tokens
        )
        return DigestResult(
            summary=result.output.summary,
            keypoints=result.output.keypoints,
            questions=[
                DigestQuestion(q.question, q.answer) for q in result.output.questions_and_answers
            ],
        )

    async def generate_flashcard_suggestions(
        self, content: str, usage_context: AIUsageContext
    ) -> list[AIFlashcardSuggestion]:
        agent = get_flashcard_agent()
        result = await agent.run(content)
        usage = result.usage()
        await self._save_usage(
            usage_context, result.response.model_name, usage.input_tokens, usage.output_tokens
        )
        return [AIFlashcardSuggestion(question=s.question, answer=s.answer) for s in result.output]

    async def _respond(
        self,
        agent: Agent[None, str],
        usage_context: AIUsageContext,
        prompt: str,
        message_history: Sequence[ModelMessage] | None = None,
    ) -> tuple[str, SerializedMessageHistory]:
        result = await agent.run(user_prompt=prompt, message_history=message_history)
        usage = result.usage()
        await self._save_usage(
            usage_context, result.response.model_name, usage.input_tokens, usage.output_tokens
        )
        serialized: SerializedMessageHistory = to_jsonable_python(result.all_messages())
        return result.output, serialized

    async def start_quiz(
        self, chapter_content: str, question_count: int, usage_context: AIUsageContext
    ) -> tuple[str, SerializedMessageHistory]:
        agent = get_quiz_agent()
        chapter_content = truncate_chapter_content(
            chapter_content, chapter_id=chapter_id_of(usage_context)
        )
        prompt = f"The reader wants to be quizzed on this chapter. Ask {question_count} questions total.\n\n--- CHAPTER CONTENT ---\n{chapter_content}"
        return await self._respond(agent, usage_context, prompt=prompt)

    async def continue_quiz(
        self,
        user_message: str,
        message_history: SerializedMessageHistory,
        usage_context: AIUsageContext,
    ) -> tuple[str, SerializedMessageHistory]:
        agent = get_quiz_agent()
        restored = ModelMessagesTypeAdapter.validate_python(message_history)
        return await self._respond(
            agent, usage_context, prompt=user_message, message_history=restored
        )

    def seed_chat_context(
        self, chapter_content: str, assistant_opener: str, *, chapter_id: int
    ) -> SerializedMessageHistory:
        """Build an initial chat history seeded with the chapter content, without
        calling the model. The content is stored as the opening user turn (paired
        with the fixed opener as the assistant turn) so that later continue_chat
        calls have the chapter in context."""
        chapter_content = truncate_chapter_content(chapter_content, chapter_id=chapter_id)
        prompt = f"The reader wants to chat about the contents of this chapter.\n\n--- CHAPTER CONTENT ---\n{chapter_content}"
        messages: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content=prompt)]),
            ModelResponse(parts=[TextPart(content=assistant_opener)]),
        ]
        return to_jsonable_python(messages)

    async def continue_chat(
        self,
        user_message: str,
        message_history: SerializedMessageHistory,
        usage_context: AIUsageContext,
    ) -> tuple[str, SerializedMessageHistory]:
        agent = get_chat_agent()
        restored = ModelMessagesTypeAdapter.validate_python(message_history)
        return await self._respond(
            agent, usage_context, prompt=user_message, message_history=restored
        )
