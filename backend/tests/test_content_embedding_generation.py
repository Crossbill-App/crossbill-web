"""Tests for the embedding job's use case, run against the real content source and index.

No endpoint reaches this use case -- the worker builds it by hand -- so it is
driven directly, with only the embedding model faked.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.commands.generate_content_embeddings_use_case import (
    GenerateContentEmbeddingsUseCase,
)
from src.application.semantic.content_type import ContentType
from src.config import get_settings
from src.infrastructure.semantic.content.content_source import ContentSource
from src.infrastructure.semantic.repositories.embedding_repository import EmbeddingRepository
from src.models import Book, Embedding, Highlight
from tests.conftest import plant_highlight
from tests.fakes import FakeEmbeddingClient
from tests.semantic_helpers import TEST_MODEL_NAME, content_hash, plant_indexed_highlight

PLANTED_VECTOR = [0.1, 0.2]
FRESH_VECTOR = [0.3, 0.4]


class ShortEmbeddingClient(FakeEmbeddingClient):
    """Returns one vector fewer than it was asked for."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return (await super().embed(texts))[:-1]


def build_use_case(
    db: AsyncSession, client: FakeEmbeddingClient, model_name: str = TEST_MODEL_NAME
) -> GenerateContentEmbeddingsUseCase:
    settings = get_settings().model_copy(update={"EMBEDDING_MODEL_NAME": model_name})
    return GenerateContentEmbeddingsUseCase(
        content_source=ContentSource(db=db, settings=settings),
        client=client,
        repo=EmbeddingRepository(db=db),
        settings=settings,
    )


@pytest.fixture
def model() -> FakeEmbeddingClient:
    return FakeEmbeddingClient(vector=FRESH_VECTOR)


@pytest.fixture
def use_case(
    db_session: AsyncSession, model: FakeEmbeddingClient
) -> GenerateContentEmbeddingsUseCase:
    return build_use_case(db_session, model)


async def stored_vectors(db: AsyncSession) -> dict[int, list[float]]:
    """Highlight id -> stored vector, for every highlight embedding in the index."""
    rows = (
        await db.execute(
            select(Embedding).where(Embedding.content_type == ContentType.HIGHLIGHT.value)
        )
    ).scalars()
    return {row.content_id: list(row.embedding) for row in rows}


async def embed(use_case: GenerateContentEmbeddingsUseCase, *highlights: Highlight) -> None:
    await use_case.execute(ContentType.HIGHLIGHT, [highlight.id for highlight in highlights])


class TestIdempotency:
    async def test_skips_content_whose_hash_and_model_are_unchanged(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        model: FakeEmbeddingClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        current = await plant_indexed_highlight(
            db_session, test_book, "unchanged", vector=PLANTED_VECTOR
        )

        await embed(use_case, current)

        assert model.calls == []
        assert await stored_vectors(db_session) == {current.id: PLANTED_VECTOR}

    async def test_embeds_and_stores_content_with_no_embedding(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        model: FakeEmbeddingClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        fresh = await plant_highlight(db_session, test_book, "never indexed")

        await embed(use_case, fresh)

        assert model.calls == [["never indexed"]]
        row = (await db_session.execute(select(Embedding))).scalar_one()
        assert (row.content_id, row.book_id, list(row.embedding)) == (
            fresh.id,
            test_book.id,
            FRESH_VECTOR,
        )
        assert (row.content_hash, row.model_name) == (
            content_hash("never indexed"),
            TEST_MODEL_NAME,
        )

    async def test_re_embeds_content_whose_text_changed(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        model: FakeEmbeddingClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        edited = await plant_indexed_highlight(
            db_session, test_book, "the edited text", hashed_text="the original text"
        )

        await embed(use_case, edited)

        assert model.calls == [["the edited text"]]
        assert await stored_vectors(db_session) == {edited.id: FRESH_VECTOR}

    async def test_re_embeds_content_indexed_under_another_model(
        self, model: FakeEmbeddingClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        indexed = await plant_indexed_highlight(db_session, test_book, "same text")

        await embed(build_use_case(db_session, model, model_name="a-newer-model"), indexed)

        assert model.calls == [["same text"]]
        assert await stored_vectors(db_session) == {indexed.id: FRESH_VECTOR}

    async def test_deletes_the_embedding_of_deleted_content(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        model: FakeEmbeddingClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        gone = await plant_indexed_highlight(db_session, test_book, "since deleted", deleted=True)

        await embed(use_case, gone)

        assert model.calls == []
        assert await stored_vectors(db_session) == {}


class TestSliceHandling:
    async def test_embeds_a_whole_slice_in_one_model_call(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        model: FakeEmbeddingClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """The point of the slice: N units cost one provider request, not N."""
        vectors = {"text 1": [1.0, 0.0], "text 2": [0.0, 1.0], "text 3": [0.5, 0.5]}
        model.vectors = vectors
        slice_ = [await plant_highlight(db_session, test_book, text) for text in vectors]

        await embed(use_case, *slice_)

        assert model.calls == [list(vectors)]
        assert await stored_vectors(db_session) == {
            highlight.id: vectors[highlight.text] for highlight in slice_
        }

    async def test_embeds_only_the_stale_members_of_a_slice(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        model: FakeEmbeddingClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """One stale unit must not pay to re-embed its current neighbours."""
        first = await plant_indexed_highlight(db_session, test_book, "current one")
        stale = await plant_highlight(db_session, test_book, "stale")
        last = await plant_indexed_highlight(db_session, test_book, "current two")

        await embed(use_case, first, stale, last)

        assert model.calls == [["stale"]]
        assert await stored_vectors(db_session) == {
            first.id: PLANTED_VECTOR,
            stale.id: FRESH_VECTOR,
            last.id: PLANTED_VECTOR,
        }

    async def test_prunes_the_dead_members_and_embeds_the_rest(
        self,
        use_case: GenerateContentEmbeddingsUseCase,
        model: FakeEmbeddingClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        """Orphan sweep and real work can arrive in one slice, and both happen."""
        dead = await plant_indexed_highlight(db_session, test_book, "gone", deleted=True)
        alive = await plant_highlight(db_session, test_book, "alive")

        await embed(use_case, dead, alive)

        assert model.calls == [["alive"]]
        assert await stored_vectors(db_session) == {alive.id: FRESH_VECTOR}

    async def test_writes_nothing_when_the_model_returns_too_few_vectors(
        self, db_session: AsyncSession, test_book: Book
    ) -> None:
        """A short vector list must not silently write embeddings for a prefix."""
        slice_ = [await plant_highlight(db_session, test_book, f"text {n}") for n in (1, 2)]
        use_case = build_use_case(db_session, ShortEmbeddingClient())

        with pytest.raises(ValueError, match="zip"):
            await embed(use_case, *slice_)

        assert await stored_vectors(db_session) == {}
