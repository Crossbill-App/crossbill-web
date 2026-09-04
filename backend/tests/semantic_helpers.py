"""Shared setup for the API tests over the embeddings index.

The global-search/related suite and the backfill suite both plant highlights, index
them, and drive endpoints gated by the embeddings feature flag. Keeping that
here stops the two files repeating each other -- and stops them drifting on what
"an indexed highlight" means.
"""

import hashlib
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, Response
from httpx._types import PrimitiveData
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.application.semantic.content_type import ContentType
from src.config import get_settings
from src.infrastructure.notes.orm.associations import note_books
from src.models import Book, Chapter, ChapterDigest, Embedding, Highlight, Note
from tests.conftest import create_test_highlight

#: Patch target for the feature flag the search and semantic routers gate on.
ENABLED = "src.infrastructure.common.dependencies.is_embeddings_enabled"

#: The model an "indexed" fixture is indexed under, and the one the gate below
#: configures. One constant rather than whatever the ambient config happens to
#: say: an embedding planted under a different model name is model-stale by
#: definition, so plant and check have to agree or every fixture reads as stale.
TEST_MODEL_NAME = "test-embedding-model"


@contextmanager
def _embedding_provider(provider: str | None) -> Iterator[None]:
    """Force the embedding feature gate on or off for the duration of the block.

    Production reads the flag through two doors, and this closes both. The
    routers gate on ``is_embeddings_enabled()``, which walks the lru-cached
    module-level settings; ``EmbeddingEnqueuer`` gates on the ``Settings``
    object the DI container snapshotted at import. Moving only one leaves a test
    asserting an enqueue that never happens -- or, worse, passing while
    asserting one does not.

    Both directions are forced explicitly because the ambient value is not the
    same everywhere: a developer with EMBEDDING_PROVIDER in a ``.env`` above the
    repo runs the suite with embeddings on, CI runs it with them off. A test
    that leant on the default would pass on one and fail on the other.

    The embedding client is a Singleton, so a cached instance built from the
    real settings would survive the override and defeat the point.
    """
    from src.core import container  # noqa: PLC0415

    container.settings.override(
        get_settings().model_copy(
            update={
                "EMBEDDING_PROVIDER": provider,
                "EMBEDDING_MODEL_NAME": TEST_MODEL_NAME,
                "EMBEDDING_BASE_URL": "http://localhost:11434",
            }
        )
    )
    container.shared.reset_singletons()
    try:
        with patch(ENABLED, return_value=provider is not None):
            yield
    finally:
        container.settings.reset_last_overriding()
        container.shared.reset_singletons()


def embeddings_enabled() -> AbstractContextManager[None]:
    """Embeddings are configured inside this block: routers answer, writes enqueue."""
    return _embedding_provider("ollama")


def embeddings_disabled() -> AbstractContextManager[None]:
    """No embedding provider inside this block: routers refuse, writes enqueue nothing."""
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
            model_name=TEST_MODEL_NAME,
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


async def plant_indexed_note(
    db: AsyncSession,
    user_id: int,
    title: str,
    *,
    body: str = "",
    kind: str | None = None,
    books: tuple[Book, ...] = (),
    vector: list[float] | None = None,
) -> Note:
    """Create a note, link it to books, and index it.

    ``book_id`` on the embedding follows the production rule: set only when the
    note links to exactly one book, because no single value is correct otherwise.
    """
    settings = get_settings()
    note = Note(user_id=user_id, title=title, body=body, kind=kind)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    for linked in books:
        await db.execute(note_books.insert().values(note_id=note.id, book_id=linked.id))
    await db.commit()

    db.add(
        Embedding(
            user_id=user_id,
            content_type=ContentType.NOTE.value,
            content_id=note.id,
            note_id=note.id,
            book_id=books[0].id if len(books) == 1 else None,
            embedding=vector if vector is not None else [0.1, 0.2],
            model_name=TEST_MODEL_NAME,
            model_version=settings.EMBEDDING_MODEL_VERSION,
            content_hash=content_hash(f"{title}\n\n{body}" if body else title),
        )
    )
    await db.commit()
    return note


async def plant_indexed_digest(
    db: AsyncSession,
    book: Book,
    chapter_name: str,
    *,
    chapter_number: int | None = None,
    summary: str = "A summary",
    keypoints: list[str] | None = None,
    vector: list[float] | None = None,
) -> tuple[Chapter, ChapterDigest]:
    """Create a chapter with a digest and index the digest."""
    settings = get_settings()
    points = keypoints if keypoints is not None else ["one", "two"]
    chapter = Chapter(book_id=book.id, name=chapter_name, chapter_number=chapter_number)
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)

    digest = ChapterDigest(
        chapter_id=chapter.id,
        summary=summary,
        keypoints=points,
        questions=[],
        generated_at=datetime.now(UTC),
        ai_model="test",
    )
    db.add(digest)
    await db.commit()
    await db.refresh(digest)

    joined = "\n".join(points)
    db.add(
        Embedding(
            user_id=book.user_id,
            content_type=ContentType.DIGEST.value,
            content_id=digest.id,
            digest_id=digest.id,
            book_id=book.id,
            embedding=vector if vector is not None else [0.1, 0.2],
            model_name=TEST_MODEL_NAME,
            model_version=settings.EMBEDDING_MODEL_VERSION,
            content_hash=content_hash(f"{summary}\n\n{joined}" if joined else summary),
        )
    )
    await db.commit()
    return chapter, digest


async def plant_one_of_each_type(
    db: AsyncSession, book: Book
) -> tuple[Highlight, Note, ChapterDigest]:
    """Index one unit of every content type, fanned out along one arc of vectors.

    Ranking is driven by the vectors alone, so the texts are arbitrary; what
    matters is that the three sort in the returned order against ``[1.0, 0.0]``
    and land in three different groups.
    """
    highlight = await plant_indexed_highlight(db, book, "a highlight", vector=[1.0, 0.0])
    note = await plant_indexed_note(db, book.user_id, "A Note", books=(book,), vector=[0.9, 0.1])
    _, digest = await plant_indexed_digest(
        db, book, "Chapter One", chapter_number=1, vector=[0.8, 0.2]
    )
    return highlight, note, digest


async def upload_highlights(
    plugin_client: AsyncClient, client_book_id: str, *texts: str
) -> dict[str, PrimitiveData]:
    """Upload highlights through the API -- the one write path that opens a batch."""
    response = await plugin_client.post(
        "/api/v1/highlights/sync",
        json={
            "client_book_id": client_book_id,
            "highlights": [
                {"text": text, "page": index, "datetime": f"2024-01-15 14:30:{index:02d}"}
                for index, text in enumerate(texts)
            ],
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def get_search(client: AsyncClient, **params: PrimitiveData) -> Response:
    """GET /search with the feature flag forced on. Status not asserted."""
    with embeddings_enabled():
        return await client.get("/api/v1/search", params={"q": "idea", **params})


async def search_groups(client: AsyncClient, **params: PrimitiveData) -> dict[str, Any]:
    """Search and return the grouped body, asserting the request succeeded."""
    response = await get_search(client, **params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def search_books(client: AsyncClient, **params: PrimitiveData) -> list[dict[str, Any]]:
    """Search and return the books matched by title or author, in title order."""
    return (await search_groups(client, **params))["books"]


async def search_highlight_ids(client: AsyncClient, **params: PrimitiveData) -> list[int]:
    """Search and return the matched highlight ids, in ranking order."""
    return [item["id"] for item in (await search_groups(client, **params))["highlights"]]


async def get_related(client: AsyncClient, **params: PrimitiveData) -> Response:
    """GET /semantic/related with the feature flag forced on."""
    with embeddings_enabled():
        return await client.get("/api/v1/semantic/related", params=params)


async def related_groups(client: AsyncClient, **params: PrimitiveData) -> dict[str, Any]:
    """Fetch related content and return the grouped body, asserting the request succeeded."""
    response = await get_related(client, **params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def backfill_enqueued_ids(client: AsyncClient, queue: AsyncMock) -> set[int]:
    """Run a backfill and return the content ids it enqueued, across every slice.

    Also pins the invariant that the batch is sized to the number of *jobs*
    enqueued -- one per slice, not one per unit -- so callers only have to assert
    *which* units were picked up.
    """
    with embeddings_enabled():
        response = await client.post("/api/v1/semantic/backfill")

    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    calls = queue.enqueue.await_args_list
    enqueued = {content_id for call in calls for content_id in call.kwargs["content_ids"]}
    assert response.json()["total_jobs"] == len(calls)
    return enqueued
