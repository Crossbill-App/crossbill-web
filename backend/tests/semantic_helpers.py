"""Shared setup for the semantic-search API tests.

The backfill suite plants highlights, indexes them, and drives endpoints gated by
the embeddings feature flag. Keeping that here stops suites repeating each other
-- and stops them drifting on what "an indexed highlight" means.
"""

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.semantic.content_type import ContentType
from src.application.semantic.idempotency import current_model_name
from src.config import get_settings
from src.models import Book, Embedding, Highlight
from tests.conftest import create_test_highlight

#: Patch target for the feature flag the semantic routers gate on.
ENABLED = "src.infrastructure.common.dependencies.is_embeddings_enabled"

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


async def backfill_enqueued_ids(client: AsyncClient, queue: AsyncMock) -> set[int]:
    """Run a backfill and return the content ids it enqueued.

    Also pins the invariant that the batch is sized to what was actually
    enqueued, so callers only have to assert *which* units were picked up.
    """
    with patch(ENABLED, return_value=True):
        response = await client.post("/api/v1/semantic/backfill")

    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    enqueued = {call.kwargs["content_id"] for call in queue.enqueue.await_args_list}
    assert response.json()["total_jobs"] == len(enqueued)
    return enqueued
