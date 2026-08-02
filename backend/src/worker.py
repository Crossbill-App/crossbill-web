"""SAQ worker entrypoint.

Start with: saq src.worker.worker_settings

For embedded mode (in-process with FastAPI), use create_embedded_worker().
"""

import signal
from typing import ClassVar

import boto3
import structlog
from saq import Queue, Worker
from saq.types import Context, SettingsDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import get_settings
from src.database import get_session_factory, initialize_database
from src.infrastructure.ai.ai_service import AIService
from src.infrastructure.ai.repositories.ai_usage_repository import AIUsageRepository
from src.infrastructure.jobs.repositories.job_batch_repository import JobBatchRepository
from src.infrastructure.jobs.saq_queue import create_queue
from src.infrastructure.jobs.tasks.digest_task_handler import DigestTaskHandler
from src.infrastructure.jobs.tasks.job_lifecycle_handler import JobLifecycleHandler
from src.infrastructure.library.repositories import BookRepository
from src.infrastructure.library.repositories.chapter_repository import ChapterRepository
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.library.repositories.s3_file_repository import S3FileRepository
from src.infrastructure.library.services.epub_text_extraction_service import (
    EpubTextExtractionService,
)
from src.infrastructure.reading.repositories.chapter_digest_repository import (
    ChapterDigestRepository,
)

logger = structlog.get_logger(__name__)

_session_factory: async_sessionmaker[AsyncSession] | None = None

# Settings and queue are created lazily to avoid side effects when importing
# this module from the FastAPI app (which only needs create_embedded_worker).
_app_settings = None
_queue = None


def _get_app_settings():  # noqa: ANN202
    """Get cached settings (lazy singleton)."""
    global _app_settings  # noqa: PLW0603
    if _app_settings is None:
        _app_settings = get_settings()
    return _app_settings


def _get_queue() -> Queue:
    """Get cached SAQ queue (lazy singleton)."""
    global _queue  # noqa: PLW0603
    if _queue is None:
        _queue = create_queue(_get_app_settings().DATABASE_URL)
    return _queue


def _build_file_repo() -> S3FileRepository | FileRepository:
    """Build the appropriate file repository based on config."""
    settings = _get_app_settings()
    if settings.s3_enabled:
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
        return S3FileRepository(s3_client=client, bucket_name=settings.S3_BUCKET_NAME)  # type: ignore[arg-type]
    return FileRepository()


def _build_digest_handler(db: AsyncSession) -> DigestTaskHandler:
    """Build a DigestTaskHandler with a fresh session."""
    from src.application.reading.commands.chapter_digest.generate_chapter_digest_use_case import (  # noqa: PLC0415
        GenerateChapterDigestUseCase,
    )

    use_case = GenerateChapterDigestUseCase(
        digest_repo=ChapterDigestRepository(db=db),
        chapter_repo=ChapterRepository(db=db),
        text_extraction_service=EpubTextExtractionService(),
        book_repo=BookRepository(db=db),
        file_repo=_build_file_repo(),
        ai_digest_service=AIService(usage_repository=AIUsageRepository(db=db)),
    )
    return DigestTaskHandler(generate_digest_use_case=use_case)


async def startup(ctx: Context) -> None:
    """Initialize worker resources."""
    logger.info("worker_starting")
    settings = _get_app_settings()
    initialize_database(settings)

    global _session_factory  # noqa: PLW0603
    _session_factory = get_session_factory(settings)

    logger.info("worker_started")


async def shutdown(ctx: Context) -> None:
    """Cleanup worker resources."""
    logger.info("worker_shutting_down")
    logger.info("worker_stopped")


async def generate_chapter_digest(
    ctx: Context, *, batch_id: int, book_id: int, chapter_id: int, user_id: int
) -> None:
    """SAQ task: generate digest for a single chapter.

    Creates a fresh DB session per task invocation to avoid sharing
    sessions across concurrent coroutines.
    """
    if _session_factory is None:
        raise RuntimeError("Worker not initialized")

    async with _session_factory() as db:
        handler = _build_digest_handler(db)
        await handler.generate(
            ctx, batch_id=batch_id, book_id=book_id, chapter_id=chapter_id, user_id=user_id
        )


async def after_process(ctx: Context) -> None:
    """SAQ after_process hook: update batch progress.

    Creates a fresh DB session to avoid sharing with task coroutines.
    """
    if _session_factory is None:
        raise RuntimeError("Worker not initialized")

    async with _session_factory() as db:
        handler = JobLifecycleHandler(batch_repo=JobBatchRepository(db=db))
        await handler.after_process(ctx)


def _build_worker_settings() -> SettingsDict[Context]:
    """Build SAQ worker settings lazily (called on first access)."""
    return {
        "queue": _get_queue(),
        "functions": [generate_chapter_digest],
        "concurrency": _get_app_settings().WORKER_CONCURRENCY,
        "startup": startup,
        "shutdown": shutdown,
        "after_process": after_process,
    }


def __getattr__(name: str) -> SettingsDict[Context]:
    """Module-level __getattr__ for lazy worker_settings access.

    SAQ CLI does ``import src.worker; src.worker.worker_settings`` which
    triggers this on first access, keeping the import itself side-effect-free.
    """
    if name == "worker_settings":
        return _build_worker_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class EmbeddedWorker(Worker[Context]):
    """SAQ Worker that skips signal handler registration.

    When running inside the FastAPI process, uvicorn owns SIGINT/SIGTERM.
    The app lifespan calls worker.stop() on shutdown instead.
    """

    SIGNALS: ClassVar[list[signal.Signals]] = []


def create_embedded_worker(queue: Queue, concurrency: int = 2) -> EmbeddedWorker:
    """Create a Worker instance for running inside the app process."""
    return EmbeddedWorker(
        queue=queue,
        functions=[generate_chapter_digest],
        concurrency=concurrency,
        startup=[startup],
        shutdown=[shutdown],
        after_process=after_process,
    )
