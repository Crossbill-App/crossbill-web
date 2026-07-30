"""Export the app's OpenAPI schema to a committed file, without a running server.

The exported ``backend/openapi.json`` is the API contract the frontend's
generated client is built from: ``frontend/orval.config.ts`` reads it, so
regenerating the client needs no running backend. CI re-exports the schema and
fails on any diff, which surfaces a backend API change as a stale-contract
failure (and, after regeneration, a type error) in the same PR.

Usage: ``uv run python scripts/export_openapi.py [target-path]``
"""

import json
import os
import sys
from pathlib import Path

# Settings are constructed at import time in src.main, so the same env
# defaults tests/conftest.py uses must be set before importing it. None of
# these values affect the schema.
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
os.environ.setdefault(
    "REFRESH_TOKEN_SECRET_KEY",
    "test-refresh-token-secret-key-at-least-32-bytes-long",
)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from src.main import app

DEFAULT_TARGET = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(f"Wrote OpenAPI schema to {target}\n")


if __name__ == "__main__":
    main()
