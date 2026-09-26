"""Hand-written stand-ins for the external boundaries the API tests cannot reach."""

import inspect
import itertools
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

PLACEHOLDER_EPUB = b"PK\x03\x04 not really an EPUB"


@dataclass(frozen=True)
class EnqueuedJob:
    function_name: str
    retries: int
    timeout_seconds: int
    kwargs: dict[str, object]


class FakeJobQueue:
    """Records jobs, checking each enqueue against the real SAQ task's signature.

    It reports a mismatch through ``pytest.fail`` rather than raising ``TypeError``
    on purpose: the enqueue seams catch ``Exception`` and log, so a plain error
    would be swallowed here exactly as it is in production and prove nothing.
    """

    def __init__(self) -> None:
        self.enqueued: list[EnqueuedJob] = []
        self.aborted: list[str] = []
        self.fail_after: int | None = None
        self._keys = itertools.count()

    async def enqueue(
        self,
        function_name: str,
        retries: int = 3,
        timeout_seconds: int = 300,
        **kwargs: object,
    ) -> str:
        _check_task_signature(function_name, kwargs)
        if self.fail_after is not None and len(self.enqueued) >= self.fail_after:
            raise RuntimeError("queue is down")
        self.enqueued.append(EnqueuedJob(function_name, retries, timeout_seconds, kwargs))
        return f"saq:test:{next(self._keys)}"

    async def abort(self, job_key: str) -> None:
        self.aborted.append(job_key)

    def jobs(self, function_name: str) -> list[EnqueuedJob]:
        return [job for job in self.enqueued if job.function_name == function_name]


def _check_task_signature(function_name: str, kwargs: dict[str, object]) -> None:
    from src import worker  # noqa: PLC0415

    task = getattr(worker, function_name, None)
    if task is None:
        return
    try:
        # SimpleNamespace stands in for the ctx SAQ passes positionally.
        inspect.signature(task).bind(SimpleNamespace(), **kwargs)
    except TypeError as exc:
        pytest.fail(f"enqueue({function_name!r}) does not match the task: {exc}")


@dataclass
class FakeEmbeddingClient:
    """Answers a text from ``vectors``, else with ``vector``; records each batch it embedded."""

    vector: list[float] = field(default_factory=lambda: [1.0, 0.0])
    vectors: dict[str, list[float]] = field(default_factory=dict)
    calls: list[list[str]] = field(default_factory=list)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [list(self.vectors.get(text, self.vector)) for text in texts]


@dataclass
class FakeTextExtraction:
    """Extracts ``text`` from any EPUB, whatever the positions."""

    text: str = "The chapter is about testing."

    def extract_text(self, epub_content: bytes, start_xpoint: str, end_xpoint: str) -> str:
        return self.text

    def extract_chapter_text(
        self, epub_content: bytes, start_xpoint: str, end_xpoint: str | None
    ) -> str:
        return self.text


class StubFileRepository:
    """Serves the same placeholder EPUB for every file and stores nothing."""

    async def save_epub(self, filename: str, content: bytes) -> str:
        return filename

    async def save_cover(self, filename: str, content: bytes) -> str:
        return filename

    async def delete_epub(self, filename: str | None) -> bool:
        return True

    async def delete_cover(self, filename: str | None) -> bool:
        return True

    async def get_epub(self, filename: str | None) -> bytes | None:
        return PLACEHOLDER_EPUB

    async def get_cover(self, filename: str | None) -> bytes | None:
        return None
