from typing import Protocol

from src.application.ai.ai_usage_context import AIUsageContext
from src.domain.common.types import SerializedMessageHistory


class AIChatServiceProtocol(Protocol):
    def seed_chat_context(
        self, chapter_content: str, assistant_opener: str, *, chapter_id: int
    ) -> SerializedMessageHistory: ...

    async def continue_chat(
        self,
        user_message: str,
        message_history: SerializedMessageHistory,
        usage_context: AIUsageContext,
    ) -> tuple[str, SerializedMessageHistory]: ...
