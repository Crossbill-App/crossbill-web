"""Tests for migration 076, which is a caller and nothing else.

What it does is covered by ``test_readium_backfill``; what is left here is the
two properties the migration itself has to hold: that importing it drags in no
application code, and that it completes when the entry point it calls is gone.
The module is loaded from its path, because ``alembic/versions`` is not a package.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

import pytest

RUNNER_MODULE = "src.infrastructure.web_reader.readium_backfill"


def _load_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "076_readium_rows_for_existing_books.py"
    )
    spec = importlib.util.spec_from_file_location("readium_backfill_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


def test_no_application_code_is_imported_at_module_level() -> None:
    # Alembic imports every file under ``versions`` to build its revision graph.
    imported_from_app = [
        name
        for name, value in vars(migration).items()
        if str(getattr(value, "__module__", "") or "").startswith("src")
    ]
    assert imported_from_app == []


def test_an_entry_point_that_cannot_be_imported_skips_the_run(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A later refactor may delete the use case; the upgrade must still complete."""
    # A ``None`` in ``sys.modules`` is how the import system spells "not there".
    monkeypatch.setitem(sys.modules, RUNNER_MODULE, None)  # pyright: ignore[reportArgumentType]

    with caplog.at_level(logging.INFO, logger="alembic.readium_backfill"):
        migration._run()

    assert [record.message for record in caplog.records if "skipped" in record.message] != []
