"""Stand-ins for the pydantic-ai agents ``AIService`` runs."""

from types import SimpleNamespace
from typing import Any

from pydantic_ai import ModelMessage
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

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
