"""Tests for embedding jobs enqueued as a side effect of a write.

The subject is the seam, not the embedding: what these pin is *which* units a
create, an edit or an upload hands to the queue, and -- at least as important --
that a queue which is off or broken never costs the user their write.

``embeddings_enabled`` / ``embeddings_disabled`` move the feature gate, which
production reads through two doors; the helper closes both.
"""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.application.reading.protocols.ai_digest_service import DigestResult
from src.domain.reading.entities.chapter_digest import DigestQuestion
from src.models import Book, Chapter, Note
from tests.conftest import CreateBookFunc, create_test_chapter
from tests.semantic_helpers import (
    embeddings_disabled,
    embeddings_enabled,
    upload_highlights,
)

#: Patch target for the slice size, so an upload can be cut into several jobs
#: without posting 33 highlights.
SLICE_SIZE = "src.application.semantic.batching.EMBEDDING_SLICE_SIZE"

#: The passage the revival tests delete or withhold and then mark again.
REHIGHLIGHTED_TEXT = "first idea"


def embedding_calls(job_queue: AsyncMock) -> list[dict[str, Any]]:
    """The kwargs of every embedding enqueue, ignoring any other task."""
    return [
        call.kwargs
        for call in job_queue.enqueue.await_args_list
        if call.args and call.args[0] == "generate_content_embeddings"
    ]


async def create_note(client: AsyncClient, book: Book) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/notes",
        json={"title": "Guilt", "body": "The axe is a symbol", "book_id": book.id},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["note"]


async def upload_one_highlight(
    client: AsyncClient, db_session: AsyncSession, job_queue: AsyncMock
) -> models.Highlight:
    """Upload REHIGHLIGHTED_TEXT and hand back its row, with the queue reset after."""
    await upload_highlights(client, "book-1", REHIGHLIGHTED_TEXT)
    stored = (await db_session.execute(select(models.Highlight))).scalars().one()
    job_queue.enqueue.reset_mock()
    return stored


async def rehighlight(client: AsyncClient, removed_ids: list[int] | None = None) -> dict[str, Any]:
    """Push REHIGHLIGHTED_TEXT as a highlight the device made after its last pull."""
    response = await client.post(
        "/api/v1/highlights/upload",
        json={
            "client_book_id": "book-1",
            "removed_ids": removed_ids or [],
            "highlights": [
                {
                    "text": REHIGHLIGHTED_TEXT,
                    "datetime": "2024-01-15 14:30:00",
                    "is_new": True,
                }
            ],
        },
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


class TestNoteWrites:
    async def test_create_enqueues_one_bare_job_for_the_note(
        self, client: AsyncClient, job_queue: AsyncMock, db_session: AsyncSession, test_book: Book
    ) -> None:
        """One job, and no batch: a single edit has no progress worth tracking.

        The kwargs are pinned by equality, so the absent ``batch_id`` is part of
        the assertion -- a JobBatch per note save would put a row in the batch
        table for every edit, each of them a batch of one.
        """
        with embeddings_enabled():
            note = await create_note(client, test_book)

        assert embedding_calls(job_queue) == [
            {
                "retries": 3,
                "timeout_seconds": 300,
                "content_type": "note",
                "content_ids": [note["id"]],
                "user_id": test_book.user_id,
            }
        ]
        batches = (await db_session.execute(select(models.JobBatchModel))).scalars().all()
        assert batches == []

    async def test_update_re_enqueues_the_edited_note(
        self, client: AsyncClient, job_queue: AsyncMock, test_book: Book
    ) -> None:
        with embeddings_enabled():
            note = await create_note(client, test_book)
            response = await client.put(
                f"/api/v1/notes/{note['id']}",
                json={"title": "Guilt", "body": "The axe is the point"},
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["note"]["body"] == "The axe is the point"
        assert [call["content_ids"] for call in embedding_calls(job_queue)] == [
            [note["id"]],
            [note["id"]],
        ]

    async def test_nothing_is_enqueued_while_embeddings_are_disabled(
        self, client: AsyncClient, job_queue: AsyncMock, db_session: AsyncSession, test_book: Book
    ) -> None:
        """A server with no embedding provider: the note is written, just not indexed."""
        with embeddings_disabled():
            note = await create_note(client, test_book)

        assert embedding_calls(job_queue) == []
        stored = (
            await db_session.execute(select(Note).filter_by(id=note["id"]))
        ).scalar_one_or_none()
        assert stored is not None

    async def test_a_broken_queue_does_not_fail_the_write(
        self, client: AsyncClient, job_queue: AsyncMock, db_session: AsyncSession, test_book: Book
    ) -> None:
        """The whole point of the seam: a missed embedding costs a backfill, not a note.

        Backfill reconciles whatever this drops, so swallowing is the correct
        behaviour rather than a shortcut.
        """
        job_queue.enqueue.side_effect = RuntimeError("redis is down")

        with embeddings_enabled():
            note = await create_note(client, test_book)

        stored = (
            await db_session.execute(select(Note).filter_by(id=note["id"]))
        ).scalar_one_or_none()
        assert stored is not None
        assert stored.title == "Guilt"


class TestHighlightUpload:
    async def test_enqueues_a_batch_covering_exactly_the_created_highlights(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})

        with embeddings_enabled():
            result = await upload_highlights(client, "book-1", "first idea", "second idea")

        assert result["highlights_created"] == 2
        stored_ids = set(
            (await db_session.execute(select(models.Highlight.id))).scalars().all(),
        )
        calls = embedding_calls(job_queue)
        assert {content_id for call in calls for content_id in call["content_ids"]} == stored_ids
        assert {call["content_type"] for call in calls} == {"highlight"}

    async def test_skipped_duplicates_are_not_re_enqueued(
        self, client: AsyncClient, job_queue: AsyncMock, create_book_via_api: CreateBookFunc
    ) -> None:
        """A KOReader sync resends the whole book, so this is the common case.

        Enqueuing the deduplicated ids would mean re-embedding every highlight
        in a book on every sync -- the job would find them current and skip, but
        only after a queue round trip each.
        """
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})

        with embeddings_enabled():
            await upload_highlights(client, "book-1", "first idea")
            job_queue.enqueue.reset_mock()
            second = await upload_highlights(client, "book-1", "first idea", "second idea")

        assert (second["highlights_created"], second["highlights_skipped"]) == (1, 1)
        assert len(embedding_calls(job_queue)) == 1
        assert len(embedding_calls(job_queue)[0]["content_ids"]) == 1

    async def test_batch_is_sized_to_slices_not_units(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Five highlights at two per slice is three jobs, and the batch says three."""
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})

        with embeddings_enabled(), patch(SLICE_SIZE, 2):
            await upload_highlights(client, "book-1", "a", "b", "c", "d", "e")

        calls = embedding_calls(job_queue)
        assert [len(call["content_ids"]) for call in calls] == [2, 2, 1]

        batch = (await db_session.execute(select(models.JobBatchModel))).scalars().one()
        assert batch.total_jobs == len(calls)
        assert batch.batch_type == "content_embedding"
        assert {call["batch_id"] for call in calls} == {batch.id}

    async def test_a_broken_queue_does_not_fail_the_upload(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})
        job_queue.enqueue.side_effect = RuntimeError("redis is down")

        with embeddings_enabled():
            result = await upload_highlights(client, "book-1", "first idea", "second idea")

        assert result["highlights_created"] == 2
        texts = (await db_session.execute(select(models.Highlight.text))).scalars().all()
        assert sorted(texts) == ["first idea", "second idea"]

    async def test_a_restored_highlight_is_enqueued_again(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """The web delete took the embedding with it, so reviving the row must bring it back."""
        book = await create_book_via_api(
            {"client_book_id": "book-1", "title": "Crime and Punishment"}
        )

        with embeddings_enabled():
            stored = await upload_one_highlight(client, db_session, job_queue)
            deletion = await client.request(
                "DELETE",
                f"/api/v1/books/{book.book_id}/highlight",
                json={"highlight_ids": [stored.id]},
            )
            assert deletion.json()["deleted_count"] == 1
            job_queue.enqueue.reset_mock()

            revived = await rehighlight(client)

        assert revived["highlights_created"] == 0
        assert [call["content_ids"] for call in embedding_calls(job_queue)] == [[stored.id]]

    async def test_a_highlight_only_returned_to_devices_is_not_enqueued_again(
        self,
        client: AsyncClient,
        job_queue: AsyncMock,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Removing a highlight from devices never touched its embedding."""
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})

        with embeddings_enabled():
            stored = await upload_one_highlight(client, db_session, job_queue)
            returned = await rehighlight(client, removed_ids=[stored.id])

        assert returned["highlights_removed"] == 1
        assert embedding_calls(job_queue) == []

    async def test_an_upload_that_creates_nothing_enqueues_nothing(
        self, client: AsyncClient, job_queue: AsyncMock, create_book_via_api: CreateBookFunc
    ) -> None:
        await create_book_via_api({"client_book_id": "book-1", "title": "Crime and Punishment"})

        with embeddings_enabled():
            await upload_highlights(client, "book-1", "first idea")
            job_queue.enqueue.reset_mock()
            repeat = await upload_highlights(client, "book-1", "first idea")

        assert repeat["highlights_created"] == 0
        assert embedding_calls(job_queue) == []


@pytest.fixture
async def digest_chapter(
    db_session: AsyncSession, test_book: Book
) -> AsyncGenerator[Chapter, None]:
    """A chapter that ``POST /chapters/{id}/digest/generate`` can actually digest.

    Needs an EPUB-backed book and chapter positions; the AI call and the text
    extraction are faked on the container so the endpoint is exercised without a
    model or a real EPUB.
    """
    from src.core import container  # noqa: PLC0415

    test_book.file_type = "epub"
    test_book.ebook_file = "book.epub"
    chapter = await create_test_chapter(db_session, test_book, "Part One", chapter_number=1)
    chapter.start_xpoint = "/body/DocFragment[1]"
    chapter.end_xpoint = "/body/DocFragment[2]"
    await db_session.commit()

    # MagicMock, not AsyncMock: extract_chapter_text is a synchronous protocol
    # method, and the text is comfortably past the use case's 50-character floor
    # for "worth digesting".
    extraction = MagicMock()
    extraction.extract_chapter_text.return_value = (
        "Raskolnikov paces his garret and talks himself into the theory that "
        "some men are permitted to step over the line."
    )

    ai_service = AsyncMock()
    ai_service.generate_digest.return_value = DigestResult(
        summary="Raskolnikov commits the murder",
        keypoints=["Poverty", "Theory of the extraordinary man"],
        questions=[DigestQuestion(question="Why?", answer="Pride")],
    )

    file_repo = AsyncMock()
    file_repo.get_epub.return_value = b"PK\x03\x04 not really an epub"

    container.shared.ebook_text_extraction_service.override(extraction)
    container.shared.ai_service.override(ai_service)
    container.shared.file_repository.override(file_repo)
    yield chapter
    container.shared.file_repository.reset_last_overriding()
    container.shared.ai_service.reset_last_overriding()
    container.shared.ebook_text_extraction_service.reset_last_overriding()


async def generate_chapter_digest(client: AsyncClient, chapter: Chapter) -> dict[str, Any]:
    with patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True):
        response = await client.post(f"/api/v1/chapters/{chapter.id}/digest/generate")
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


class TestDigestGeneration:
    async def test_enqueues_the_generated_digest(
        self, client: AsyncClient, job_queue: AsyncMock, digest_chapter: Chapter, test_book: Book
    ) -> None:
        with embeddings_enabled():
            digest = await generate_chapter_digest(client, digest_chapter)

        assert digest["summary"] == "Raskolnikov commits the murder"
        assert embedding_calls(job_queue) == [
            {
                "retries": 3,
                "timeout_seconds": 300,
                "content_type": "digest",
                "content_ids": [digest["id"]],
                "user_id": test_book.user_id,
            }
        ]

    async def test_answering_the_questions_does_not_re_enqueue(
        self, client: AsyncClient, job_queue: AsyncMock, digest_chapter: Chapter
    ) -> None:
        """Only summary and keypoints are embedded, so an answer cannot stale it."""
        with embeddings_enabled():
            await generate_chapter_digest(client, digest_chapter)
            job_queue.enqueue.reset_mock()
            response = await client.put(
                f"/api/v1/chapters/{digest_chapter.id}/digest/answers",
                json={"answers": [{"question_index": 0, "user_answer": "Poverty"}]},
            )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert embedding_calls(job_queue) == []

    async def test_a_broken_queue_does_not_fail_the_generation(
        self, client: AsyncClient, job_queue: AsyncMock, digest_chapter: Chapter
    ) -> None:
        job_queue.enqueue.side_effect = RuntimeError("redis is down")

        with embeddings_enabled():
            digest = await generate_chapter_digest(client, digest_chapter)

        assert digest["keypoints"] == ["Poverty", "Theory of the extraordinary man"]
