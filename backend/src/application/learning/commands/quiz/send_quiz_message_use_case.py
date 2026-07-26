import structlog

from src.application.ai.ai_usage_context import AIUsageContext
from src.application.learning.protocols.ai_chat_session_repository import (
    AIChatSessionRepositoryProtocol,
)
from src.application.learning.protocols.ai_quiz_service import AIQuizServiceProtocol
from src.domain.common.value_objects.ids import AIChatSessionId, UserId
from src.domain.learning.exceptions import QuizSessionNotFoundError

logger = structlog.get_logger(__name__)


class SendQuizMessageUseCase:
    def __init__(
        self,
        ai_chat_session_repository: AIChatSessionRepositoryProtocol,
        ai_quiz_service: AIQuizServiceProtocol,
    ) -> None:
        self.ai_chat_session_repo = ai_chat_session_repository
        self.ai_quiz_service = ai_quiz_service

    async def send(self, session_id: int, user_message: str, user_id: int) -> str:
        """Send a message to an existing quiz session.

        Returns:
            The AI response message.
        """
        session_id_vo = AIChatSessionId(session_id)
        user_id_vo = UserId(user_id)

        # 1. Load session
        session = await self.ai_chat_session_repo.find_by_id(session_id_vo, user_id_vo)
        if not session:
            raise QuizSessionNotFoundError(session_id)

        # 2. Run AI with message history
        usage_context = AIUsageContext(
            user_id=user_id_vo,
            task_type="quiz",
            entity_type="chapter",
            entity_id=session.chapter_id.value,
        )
        ai_response, updated_history = await self.ai_quiz_service.continue_quiz(
            user_message, session.message_history, usage_context
        )

        # 3. Update session
        await self.ai_chat_session_repo.update_message_history(session_id_vo, updated_history)

        logger.info(
            "quiz_message_sent",
            session_id=session_id,
        )

        return ai_response
