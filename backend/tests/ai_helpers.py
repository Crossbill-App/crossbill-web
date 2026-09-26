"""Stand-ins for the pydantic-ai agents ``AIService`` runs."""

from types import SimpleNamespace
from typing import Any

from pydantic_ai import ModelMessage
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AIChatSession as AIChatSessionModel

FAKE_MODEL_NAME = "fake-model"


class FakeRunResult:
    """The parts of pydantic-ai's ``AgentRunResult`` that ``AIService`` reads."""

    def __init__(self, prompt: str, output: Any) -> None:  # noqa: ANN401
        self.output = output
        self.response = SimpleNamespace(model_name=FAKE_MODEL_NAME)
        self._prompt = prompt

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=1, output_tokens=1)

    def all_messages(self) -> list[ModelMessage]:
        return [
            ModelRequest(parts=[UserPromptPart(content=self._prompt)]),
            ModelResponse(parts=[TextPart(content=str(self.output))]),
        ]


class FakeAgent:
    """Records the prompts it was run with, and answers with a fixed output."""

    def __init__(self, output: Any) -> None:  # noqa: ANN401
        self.output = output
        self.received_prompts: list[str] = []

    async def run(
        self,
        content: str | None = None,
        *,
        user_prompt: str | None = None,
        message_history: object = None,
    ) -> FakeRunResult:
        prompt = content if content is not None else user_prompt
        assert prompt is not None, "agent run without a prompt"
        self.received_prompts.append(prompt)
        return FakeRunResult(prompt, self.output)


def digest_output(
    summary: str = "A summary.",
    keypoints: list[str] | None = None,
    questions: list[tuple[str, str]] | None = None,
) -> SimpleNamespace:
    """The shape ``generate_digest`` unpacks out of its agent's output."""
    return SimpleNamespace(
        summary=summary,
        keypoints=keypoints if keypoints is not None else ["A key point."],
        questions_and_answers=[
            SimpleNamespace(question=question, answer=answer)
            for question, answer in (questions if questions is not None else [("Q?", "A.")])
        ],
    )


def flashcard_output(cards: list[tuple[str, str]]) -> list[SimpleNamespace]:
    """The shape ``generate_flashcard_suggestions`` unpacks out of its agent's output."""
    return [SimpleNamespace(question=question, answer=answer) for question, answer in cards]


async def seeded_history(db_session: AsyncSession, session_id: int) -> str:
    """The message history the endpoint stored, as one searchable string."""
    session = (
        await db_session.execute(
            select(AIChatSessionModel).where(AIChatSessionModel.id == session_id)
        )
    ).scalar_one()
    return str(session.message_history)
