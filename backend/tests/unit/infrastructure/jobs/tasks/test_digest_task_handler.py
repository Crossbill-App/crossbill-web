"""Tests for DigestTaskHandler."""

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.jobs.tasks.digest_task_handler import DigestTaskHandler


@pytest.fixture
def generate_use_case() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def handler(generate_use_case: AsyncMock) -> DigestTaskHandler:
    return DigestTaskHandler(generate_digest_use_case=generate_use_case)


class TestDigestTaskHandler:
    async def test_calls_use_case_with_correct_ids(
        self, handler: DigestTaskHandler, generate_use_case: AsyncMock
    ) -> None:
        ctx: dict[str, object] = {}
        await handler.generate(ctx, batch_id=1, book_id=42, chapter_id=7, user_id=1)  # pyright: ignore[reportArgumentType]  # dict used in place of Context TypedDict in tests

        generate_use_case.generate_digest.assert_called_once()
        call_args = generate_use_case.generate_digest.call_args
        assert call_args.kwargs["chapter_id"].value == 7
        assert call_args.kwargs["user_id"].value == 1
