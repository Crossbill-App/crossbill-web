"""Tests for EmbeddingTaskHandler."""

from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest
import structlog
from structlog.typing import EventDict

from src.application.semantic.content_type import ContentType
from src.infrastructure.jobs.tasks.embedding_task_handler import EmbeddingTaskHandler

CTX: dict[str, object] = {}


@pytest.fixture
def generate_use_case() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def handler(generate_use_case: AsyncMock) -> EmbeddingTaskHandler:
    return EmbeddingTaskHandler(generate_embeddings_use_case=generate_use_case)


@pytest.fixture
def captured_logs() -> Generator[list[EventDict], None, None]:
    """Capture structlog events for the duration of one test."""
    with structlog.testing.capture_logs() as entries:
        yield entries


class TestEmbeddingTaskHandler:
    async def test_passes_the_whole_slice_to_the_use_case(
        self, handler: EmbeddingTaskHandler, generate_use_case: AsyncMock
    ) -> None:
        await handler.generate(
            CTX,  # pyright: ignore[reportArgumentType]  # dict stands in for the Context TypedDict
            batch_id=1,
            content_type=ContentType.NOTE,
            content_ids=[7, 8, 9],
        )

        generate_use_case.execute.assert_awaited_once_with(
            content_type=ContentType.NOTE, content_ids=[7, 8, 9]
        )


class TestFailureIsObservable:
    async def test_logs_the_slice_ids_when_the_slice_fails(
        self,
        handler: EmbeddingTaskHandler,
        generate_use_case: AsyncMock,
        captured_logs: list[EventDict],
    ) -> None:
        """A slice fails as a unit, so its ids are the only lead to the offender.

        Without this, a slice that dies on one unembeddable unit says which batch
        failed and nothing about which content caused it.
        """
        generate_use_case.execute.side_effect = RuntimeError("provider rejected the input")

        with pytest.raises(RuntimeError):
            await handler.generate(
                CTX,  # pyright: ignore[reportArgumentType]  # dict stands in for the Context TypedDict
                batch_id=3,
                content_type=ContentType.HIGHLIGHT,
                content_ids=[11, 12],
            )

        failures = [entry for entry in captured_logs if entry["event"] == "embedding_task_failed"]
        assert len(failures) == 1
        assert failures[0]["content_ids"] == [11, 12]
        assert failures[0]["content_type"] == "highlight"
        assert failures[0]["batch_id"] == 3
        assert failures[0]["log_level"] == "error"

    async def test_reraises_so_the_job_retries_and_the_batch_counts_it(
        self,
        handler: EmbeddingTaskHandler,
        generate_use_case: AsyncMock,
        captured_logs: list[EventDict],
    ) -> None:
        """Swallowing the error would report the slice as embedded when it was not."""
        generate_use_case.execute.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await handler.generate(
                CTX,  # pyright: ignore[reportArgumentType]  # dict stands in for the Context TypedDict
                batch_id=3,
                content_type=ContentType.NOTE,
                content_ids=[1],
            )

        assert not [
            entry for entry in captured_logs if entry["event"] == "embedding_task_completed"
        ]
