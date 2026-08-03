"""Shared doubles for the note command use cases.

Creating and updating a note take the same link-target and embedding
collaborators, so the mocks live here rather than being re-declared per file.
The repositories differ (create saves a new note, update loads an existing one)
and stay with their own tests.
"""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def link_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_ids.return_value = []
    return repo


@pytest.fixture
def embedding_enqueuer() -> AsyncMock:
    return AsyncMock()
