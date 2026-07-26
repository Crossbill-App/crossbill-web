"""Chat session endpoints for chapter-based AI quizzes."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status

from src.application.learning.commands.chat.send_chat_message_use_case import (
    SendChatMessageUseCase,
)
from src.application.learning.commands.chat.start_chat_session_use_case import (
    StartChatSessionUseCase,
)
from src.application.learning.commands.quiz.send_quiz_message_use_case import (
    SendQuizMessageUseCase,
)
from src.application.learning.commands.quiz.start_quiz_session_use_case import (
    StartQuizSessionUseCase,
)
from src.core import container
from src.domain.identity.entities.user import User
from src.infrastructure.common.dependencies import require_ai_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.learning.schemas.chat_schemas import (
    CreateChatSessionResponse,
    SendChatMessageRequest,
    SendChatMessageResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])


@router.post(
    "/chapters/{chapter_id}/quiz-sessions",
    response_model=CreateChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
@require_ai_enabled
async def create_quiz_session(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: StartQuizSessionUseCase = Depends(
        inject_use_case(container.learning.start_quiz_session_use_case)
    ),
) -> CreateChatSessionResponse:
    """Start a new quiz session for a chapter."""
    session_id, first_question = await use_case.start(chapter_id, current_user.id.value)
    return CreateChatSessionResponse(session_id=session_id, message=first_question)


@router.post(
    "/quiz-sessions/{session_id}/messages",
    response_model=SendChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
@require_ai_enabled
async def send_quiz_message(
    session_id: int,
    body: SendChatMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: SendQuizMessageUseCase = Depends(
        inject_use_case(container.learning.send_quiz_message_use_case)
    ),
) -> SendChatMessageResponse:
    """Send a message to an existing quiz session."""
    ai_response = await use_case.send(session_id, body.message, current_user.id.value)
    return SendChatMessageResponse(message=ai_response)


@router.post(
    "/chapters/{chapter_id}/chat-sessions",
    response_model=CreateChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
@require_ai_enabled
async def create_chat_session(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: StartChatSessionUseCase = Depends(
        inject_use_case(container.learning.start_chat_session_use_case)
    ),
) -> CreateChatSessionResponse:
    """Start a chat session for a chapter."""
    session_id, first_question = await use_case.start(chapter_id, current_user.id.value)
    return CreateChatSessionResponse(session_id=session_id, message=first_question)


@router.post(
    "/chat-sessions/{session_id}/messages",
    response_model=SendChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
@require_ai_enabled
async def send_chat_message(
    session_id: int,
    body: SendChatMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: SendChatMessageUseCase = Depends(
        inject_use_case(container.learning.send_chat_message_use_case)
    ),
) -> SendChatMessageResponse:
    """Send a message to an existing chat session."""
    ai_response = await use_case.send(session_id, body.message, current_user.id.value)
    return SendChatMessageResponse(message=ai_response)
