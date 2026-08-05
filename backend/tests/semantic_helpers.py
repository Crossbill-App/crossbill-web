"""Shared setup for the semantic-search API tests.

The search/related suite and the backfill suite both plant highlights, index
them, and drive endpoints gated by the embeddings feature flag. Keeping that
here stops the two files repeating each other -- and stops them drifting on what
"an indexed highlight" means.
"""

import hashlib
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, Response
from httpx._types import PrimitiveData
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.semantic.content_type import ContentType
from src.application.semantic.idempotency import current_model_name
from src.config import get_settings
from src.models import Book, Embedding, Highlight
from tests.conftest import create_test_highlight

#: Patch target for the feature flag the semantic routers gate on.
ENABLED = "src.infrastructure.common.dependencies.is_embeddings_enabled"


@contextmanager
def _embedding_provider(provider: str | None) -> Iterator[None]:
    """Force the *write-path* embedding gate for the duration of the block.

    Deliberately not the same lever as ``ENABLED``. The routers gate on
    ``is_embeddings_enabled()``, which reads the lru-cached module-level
    settings; ``EmbeddingEnqueuer`` gates on the ``Settings`` object the DI
    container holds. Patching the first does nothing to a note save, so a test
    that used it would assert an enqueue that never happens -- or, worse, pass
    while asserting one does not.

    Both directions are forced explicitly because the ambient value is not the
    same everywhere: a developer with EMBEDDING_PROVIDER in a ``.env`` above the
    repo runs the suite with embeddings on, CI runs it with them off. A test
    that leant on the default would pass on one and fail on the other.
    """
    from src.core import container  # noqa: PLC0415

    container.settings.override(
        get_settings().model_copy(
            update={
                "EMBEDDING_PROVIDER": provider,
                "EMBEDDING_MODEL_NAME": "test-embedding-model",
                "EMBEDDING_BASE_URL": "http://localhost:11434",
            }
        )
    )
    try:
        yield
    finally:
        container.settings.reset_last_overriding()


def embeddings_enabled() -> AbstractContextManager[None]:
    """Write paths enqueue embeddings inside this block."""
    return _embedding_provider("ollama")


def embeddings_disabled() -> AbstractContextManager[None]:
    """Write paths must not enqueue anything inside this block."""
    return _embedding_provider(None)


_HIGHLIGHT_DATETIME = "2024-01-15 14:30:22"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def index_highlight(
    db: AsyncSession,
    book: Book,
    highlight: Highlight,
    *,
    vector: list[float] | None = None,
    hashed_text: str | None = None,
) -> None:
    """Store an embedding for a highlight, current for the configured model.

    Sets the cascade anchor the repository always writes: the foreign key and the
    CHECK both require it, so an embedding cannot be planted for content that
    does not exist.

    ``hashed_text`` overrides what the stored hash is taken over, so a caller can
    simulate content that changed after it was indexed.
    """
    settings = get_settings()
    db.add(
        Embedding(
            user_id=highlight.user_id,
            content_type=ContentType.HIGHLIGHT.value,
            content_id=highlight.id,
            highlight_id=highlight.id,
            book_id=book.id,
            embedding=vector if vector is not None else [0.1, 0.2],
            model_name=current_model_name(settings),
            model_version=settings.EMBEDDING_MODEL_VERSION,
            content_hash=content_hash(hashed_text if hashed_text is not None else highlight.text),
        )
    )
    await db.commit()


async def plant_indexed_highlight(
    db: AsyncSession,
    book: Book,
    text: str,
    *,
    vector: list[float] | None = None,
    hashed_text: str | None = None,
    deleted: bool = False,
) -> Highlight:
    """Create a highlight and its embedding — the shape most of these tests need."""
    highlight = await create_test_highlight(
        db,
        book,
        book.user_id,
        text=text,
        datetime_str=_HIGHLIGHT_DATETIME,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    await index_highlight(db, book, highlight, vector=vector, hashed_text=hashed_text)
    return highlight


async def get_search(client: AsyncClient, **params: PrimitiveData) -> Response:
    """GET /semantic/search with the feature flag forced on. Status not asserted."""
    with patch(ENABLED, return_value=True):
        return await client.get("/api/v1/semantic/search", params={"q": "idea", **params})


async def search_content_ids(client: AsyncClient, **params: PrimitiveData) -> list[int]:
    """Search and return the matched content ids, in ranking order."""
    response = await get_search(client, **params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return [row["content_id"] for row in response.json()]


async def get_related(client: AsyncClient, **params: PrimitiveData) -> Response:
    """GET /semantic/related with the feature flag forced on."""
    with patch(ENABLED, return_value=True):
        return await client.get("/api/v1/semantic/related", params=params)


async def backfill_enqueued_ids(client: AsyncClient, queue: AsyncMock) -> set[int]:
    """Run a backfill and return the content ids it enqueued, across every slice.

    Also pins the invariant that the batch is sized to the number of *jobs*
    enqueued -- one per slice, not one per unit -- so callers only have to assert
    *which* units were picked up.
    """
    with patch(ENABLED, return_value=True):
        response = await client.post("/api/v1/semantic/backfill")

    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    calls = queue.enqueue.await_args_list
    enqueued = {content_id for call in calls for content_id in call.kwargs["content_ids"]}
    assert response.json()["total_jobs"] == len(calls)
    return enqueued
