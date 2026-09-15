"""Composition root for the one-off Readium backfill that migration 076 runs.

The migration has no container and no request to borrow a session from, so the
real repositories and services are wired here by hand, the way ``src/worker.py``
does for a SAQ task.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.web_reader.commands.backfill_book_locators_use_case import (
    BackfillBookLocatorsUseCase,
)
from src.application.web_reader.commands.backfill_readium_rows_use_case import (
    BackfillReadiumRowsUseCase,
    ReadiumBackfillReport,
)
from src.config import Settings, get_settings
from src.database import dispose_engine, get_session_factory, initialize_database
from src.infrastructure.library.repositories import BookRepository
from src.infrastructure.library.repositories.file_repository_factory import build_file_repository
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.reading.repositories.highlight_repository import HighlightRepository
from src.infrastructure.reading.repositories.reading_session_repository import (
    ReadingSessionRepository,
)
from src.infrastructure.web_reader.repositories.publication_repository import PublicationRepository
from src.infrastructure.web_reader.services.xpoint_cfi_position_anchor_service import (
    XPointCfiPositionAnchorService,
)

logger = structlog.get_logger(__name__)


async def run_readium_backfill() -> ReadiumBackfillReport:
    """Derive the Readium rows of every book, over a connection pool of this run's own."""
    settings = get_settings()
    initialize_database(settings)
    try:
        session_factory = get_session_factory(settings)
        async with session_factory() as db:
            report = await _use_case(db, settings).backfill_all()
        logger.info("readium_backfill_finished", report=report)
        return report
    finally:
        # The pool belongs to this run alone -- the migration process carries on
        # over Alembic's own connection -- and nothing outlives the event loop
        # ``asyncio.run`` is about to close.
        await dispose_engine()


def _use_case(db: AsyncSession, settings: Settings) -> BackfillReadiumRowsUseCase:
    return BackfillReadiumRowsUseCase(
        book_repository=BookRepository(db=db),
        file_repository=build_file_repository(settings),
        publication_parser=EpubParserService(),
        publication_repository=PublicationRepository(db=db),
        backfill_book_locators_use_case=BackfillBookLocatorsUseCase(
            highlight_repository=HighlightRepository(db=db),
            session_repository=ReadingSessionRepository(db=db),
            position_anchor_service=XPointCfiPositionAnchorService(),
        ),
    )
