"""Tests for the chapter-content cap shared by digest, quiz and chat.

Digest already capped its input; quiz and chat did not, so a chapter with no
real chapter boundaries (the whole book parsed as one chapter) sent the
entire book as context. `truncate_chapter_content` is the one place all
three now go through.
"""

from collections.abc import Generator

import pytest
import structlog
from structlog.typing import EventDict

from src.infrastructure.ai.ai_service import (
    MAX_CHAPTER_CONTEXT_CHARS,
    truncate_chapter_content,
)


@pytest.fixture
def captured_logs() -> Generator[list[EventDict], None, None]:
    """Capture structlog events for the duration of one test."""
    with structlog.testing.capture_logs() as entries:
        yield entries


class TestTruncateChapterContent:
    def test_leaves_content_within_the_budget_untouched(
        self, captured_logs: list[EventDict]
    ) -> None:
        content = "w" * MAX_CHAPTER_CONTEXT_CHARS

        result = truncate_chapter_content(content, chapter_id=7)

        assert result == content
        assert captured_logs == []

    def test_leaves_short_content_untouched(self, captured_logs: list[EventDict]) -> None:
        result = truncate_chapter_content("short chapter", chapter_id=7)

        assert result == "short chapter"
        assert captured_logs == []

    def test_truncates_over_budget_content_to_the_cap(self) -> None:
        content = "x" * (MAX_CHAPTER_CONTEXT_CHARS * 2)

        result = truncate_chapter_content(content, chapter_id=42)

        assert len(result) == MAX_CHAPTER_CONTEXT_CHARS
        assert result == content[:MAX_CHAPTER_CONTEXT_CHARS]

    def test_logs_chapter_id_and_dropped_length_when_truncating(
        self, captured_logs: list[EventDict]
    ) -> None:
        content = "x" * (MAX_CHAPTER_CONTEXT_CHARS + 250)

        truncate_chapter_content(content, chapter_id=42)

        assert len(captured_logs) == 1
        event = captured_logs[0]
        assert event["event"] == "chapter_content_truncated"
        assert event["chapter_id"] == 42
        assert event["dropped_chars"] == 250
