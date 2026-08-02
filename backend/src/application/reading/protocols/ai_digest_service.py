from dataclasses import dataclass
from typing import Protocol

from src.application.ai.ai_usage_context import AIUsageContext
from src.domain.reading.entities.chapter_digest import DigestQuestion


@dataclass(frozen=True)
class DigestResult:
    summary: str
    keypoints: list[str]
    questions: list[DigestQuestion]


class AIDigestServiceProtocol(Protocol):
    async def generate_digest(
        self, content: str, usage_context: AIUsageContext
    ) -> DigestResult: ...
