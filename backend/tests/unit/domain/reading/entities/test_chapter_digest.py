from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import ChapterDigestId, ChapterId
from src.domain.reading.entities.chapter_digest import (
    ChapterDigest,
    DigestQuestion,
)


def _create(**overrides: Any) -> ChapterDigest:  # noqa: ANN401
    """Create ChapterDigest with sensible defaults."""
    defaults: dict[str, Any] = {
        "chapter_id": ChapterId(1),
        "summary": "This chapter covers the basics of testing.",
        "keypoints": [
            "Write tests first",
            "Keep tests simple",
            "Test behavior, not implementation",
        ],
        "questions": [
            DigestQuestion(question="What is testing?", answer="Verifying correctness."),
        ],
        "generated_at": datetime.now(UTC),
        "ai_model": "gpt-4",
    }
    defaults.update(overrides)
    return ChapterDigest.create(**defaults)  # type: ignore[arg-type]


def test_create_digest() -> None:
    content = _create()
    assert content.chapter_id == ChapterId(1)
    assert "basics of testing" in content.summary
    assert len(content.keypoints) == 3
    assert content.ai_model == "gpt-4"


def test_create_strips_whitespace() -> None:
    content = _create(
        summary="  Summary with spaces  ",
        keypoints=["  Point 1  ", "Point 2"],
        ai_model="  gpt-4  ",
    )
    assert content.summary == "Summary with spaces"
    assert content.keypoints == ["Point 1", "Point 2"]
    assert content.ai_model == "gpt-4"


def test_create_with_id() -> None:
    now = datetime.now(UTC)
    content = ChapterDigest.create_with_id(
        id=ChapterDigestId(42),
        chapter_id=ChapterId(1),
        summary="Summary",
        keypoints=["Point 1"],
        questions=[],
        generated_at=now,
        ai_model="gpt-4",
    )
    assert content.id == ChapterDigestId(42)
    assert content.generated_at == now


def test_empty_summary_raises_error() -> None:
    with pytest.raises(DomainError, match="Summary cannot be empty"):
        _create(summary="")


def test_whitespace_only_summary_raises_error() -> None:
    with pytest.raises(DomainError, match="Summary cannot be empty"):
        _create(summary="   ")


def test_empty_keypoints_raises_error() -> None:
    with pytest.raises(DomainError, match="Keypoints list cannot be empty"):
        _create(keypoints=[])


def test_empty_keypoint_string_raises_error() -> None:
    with pytest.raises(DomainError, match="Keypoints cannot contain empty strings"):
        _create(keypoints=["Point 1", "", "Point 3"])


def test_empty_ai_model_raises_error() -> None:
    with pytest.raises(DomainError, match="AI model cannot be empty"):
        _create(ai_model="")


def test_digest_question_default_user_answer() -> None:
    q = DigestQuestion(question="What?", answer="This.")
    assert q.user_answer == ""


def test_digest_question_with_user_answer() -> None:
    q = DigestQuestion(question="What?", answer="This.", user_answer="My answer")
    assert q.user_answer == "My answer"


def test_update_user_answers() -> None:
    content = _create(
        questions=[
            DigestQuestion(question="Q1?", answer="A1"),
            DigestQuestion(question="Q2?", answer="A2"),
            DigestQuestion(question="Q3?", answer="A3"),
        ]
    )
    content.update_user_answers({0: "User A1", 2: "User A3"})
    assert content.questions[0].user_answer == "User A1"
    assert content.questions[1].user_answer == ""
    assert content.questions[2].user_answer == "User A3"


def test_update_user_answers_ignores_out_of_range() -> None:
    content = _create(questions=[DigestQuestion(question="Q1?", answer="A1")])
    content.update_user_answers({0: "Valid", 5: "Invalid", -1: "Also invalid"})
    assert content.questions[0].user_answer == "Valid"
    assert len(content.questions) == 1
