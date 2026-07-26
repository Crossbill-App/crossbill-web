"""Tests for GetActiveBookBatchUseCase."""

from unittest.mock import AsyncMock

import pytest

from src.application.jobs.queries.get_active_book_batch_use_case import GetActiveBookBatchUseCase
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.jobs.entities.job_batch import JobBatchType


@pytest.fixture
def job_batch_query() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(job_batch_query: AsyncMock) -> GetActiveBookBatchUseCase:
    return GetActiveBookBatchUseCase(job_batch_query=job_batch_query)


class TestGetActiveBookBatch:
    async def test_queries_by_the_book_id_as_reference(
        self, use_case: GetActiveBookBatchUseCase, job_batch_query: AsyncMock
    ) -> None:
        job_batch_query.get_active_for_reference.return_value = None

        result = await use_case.execute(BookId(42), UserId(1), JobBatchType.CHAPTER_PREREADING)

        assert result is None
        job_batch_query.get_active_for_reference.assert_awaited_once_with(
            batch_type=JobBatchType.CHAPTER_PREREADING,
            reference_id="42",
            user_id=UserId(1),
        )
