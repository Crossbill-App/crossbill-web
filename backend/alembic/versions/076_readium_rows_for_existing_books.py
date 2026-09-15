"""Derive the publication index and the locators of every book already holding an EPUB

The ingest paths #839 and #842 added only cover new writes: a book uploaded
before them has neither a stored publication index nor a Readium Locator on any
of its highlights or reading sessions. EPUBs reach this app from the KOReader
plugin alone, so nobody will re-upload one to trigger the derivation, and the
web reader cannot open a book without it. This fills the backlog once, on
deploy.

Everything it does lives in an application use case
(``BackfillReadiumRowsUseCase``), reached through one infrastructure entry
point: the publication index is what the EPUB parser makes of an archive and a
locator is what ``xpoint-cfi`` makes of an xpointer, and neither can be restated
in SQL. Deleting or renaming that use case later must not break ``alembic
upgrade`` on every database forever, which is why the import happens inside
``_run`` rather than at module level -- Alembic loads every file in
``alembic/versions`` to build its revision graph -- and why a failing import is
one of the failures this file swallows.

Failure policy: nothing here is worth a failed deploy. Everything it derives
can be derived again -- a book with no publication index opens in the web reader
with one derived on the spot, and its highlights and reading sessions gain
locators on their next KOReader sync or EPUB upload -- so ``_run`` logs whatever
comes out and returns, and the upgrade goes on to record 076 as applied.

The run happens inside ``autocommit_block`` because it opens a connection of its
own: Alembic's default is one transaction for the whole upgrade, and the tables
these rows live in are created by migrations before this one, whose DDL a second
connection cannot see -- and whose locks it would wait on -- until that
transaction commits. The block commits it first, by documented design.

Revision ID: 076
Revises: 075
"""

import asyncio
import logging
from collections.abc import Sequence

from alembic import context, op

revision: str = "076"
down_revision: str | Sequence[str] | None = "075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# alembic.ini puts the root logger at WARNING and the ``alembic`` one at INFO,
# so a child of it is what shows up in the deploy log.
logger = logging.getLogger("alembic.readium_backfill")


def upgrade() -> None:
    """Store a publication index and locators for every book that has an EPUB."""
    if context.is_offline_mode():
        return
    with op.get_context().autocommit_block():
        _run()


def downgrade() -> None:
    """No-op: derived data, dropped with its columns by 074's and 073's downgrades."""


def _run() -> None:
    try:
        from src.infrastructure.web_reader.readium_backfill import (  # noqa: PLC0415
            run_readium_backfill,
        )

        report = asyncio.run(run_readium_backfill())
    except Exception:
        logger.exception(
            "Readium backfill skipped: a book opens in the web reader with its manifest "
            "derived on first open, and its highlights and reading sessions gain locators "
            "on their next KOReader sync or EPUB upload"
        )
        return

    logger.info("Readium backfill finished: %s", report)
