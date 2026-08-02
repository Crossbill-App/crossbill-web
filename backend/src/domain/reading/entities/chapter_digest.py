from dataclasses import dataclass
from datetime import datetime

from src.domain.common.entity import Entity
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import ChapterDigestId, ChapterId


@dataclass(frozen=True)
class DigestQuestion:
    question: str
    answer: str
    user_answer: str = ""


@dataclass
class ChapterDigest(Entity[ChapterDigestId]):
    """
    Chapter pre-reading content entity.

    Contains AI-generated summary and keypoints to help readers
    understand what to expect before reading a chapter.
    """

    # Identity
    id: ChapterDigestId
    chapter_id: ChapterId

    # Content
    summary: str
    keypoints: list[str]
    questions: list[DigestQuestion]

    # Metadata
    generated_at: datetime
    ai_model: str

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.summary or not self.summary.strip():
            raise DomainError("Summary cannot be empty")

        if not self.keypoints:
            raise DomainError("Keypoints list cannot be empty")

        if any(not kp or not kp.strip() for kp in self.keypoints):
            raise DomainError("Keypoints cannot contain empty strings")

        if not self.ai_model or not self.ai_model.strip():
            raise DomainError("AI model cannot be empty")

    def update_user_answers(self, answers: dict[int, str]) -> None:
        """Update user answers by question index. Mutates in place."""
        for index, answer_text in answers.items():
            if 0 <= index < len(self.questions):
                old_q = self.questions[index]
                self.questions[index] = DigestQuestion(
                    question=old_q.question,
                    answer=old_q.answer,
                    user_answer=answer_text,
                )

    # Factory methods
    @classmethod
    def create(
        cls,
        chapter_id: ChapterId,
        summary: str,
        keypoints: list[str],
        questions: list[DigestQuestion],
        generated_at: datetime,
        ai_model: str,
    ) -> "ChapterDigest":
        """Factory for creating new pre-reading content."""
        return cls(
            id=ChapterDigestId.generate(),
            chapter_id=chapter_id,
            summary=summary.strip(),
            keypoints=[kp.strip() for kp in keypoints],
            questions=questions,
            generated_at=generated_at,
            ai_model=ai_model.strip(),
        )

    @classmethod
    def create_with_id(
        cls,
        id: ChapterDigestId,
        chapter_id: ChapterId,
        summary: str,
        keypoints: list[str],
        questions: list[DigestQuestion],
        generated_at: datetime,
        ai_model: str,
    ) -> "ChapterDigest":
        """Factory for reconstituting from persistence."""
        return cls(
            id=id,
            chapter_id=chapter_id,
            summary=summary,
            keypoints=keypoints,
            questions=questions,
            generated_at=generated_at,
            ai_model=ai_model,
        )
