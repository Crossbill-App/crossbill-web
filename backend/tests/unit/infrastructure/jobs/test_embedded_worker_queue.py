"""The embedded worker's queue must be the one the app connected.

The invariant under test *is* a module-level global, so reaching for it is the
subject rather than a shortcut around one.
"""

# pyright: reportPrivateUsage=false

from typing import cast
from unittest.mock import MagicMock

from saq import Queue

from src import worker


def test_embedded_worker_binds_the_app_queue_as_the_module_queue() -> None:
    """Otherwise a task that enqueues follow-up work builds its own, unconnected queue.

    In embedded mode nothing else populates ``worker._queue``, so the lazy
    branch of ``_get_queue`` would run and hand back a ``Queue`` whose pool is
    never opened. Enqueuing on it raises, and the one caller that does this --
    a chapter digest enqueuing its own embedding -- swallows enqueue failures on
    purpose. The result would be digests that are silently never indexed, in the
    default configuration (``EMBEDDED_WORKER`` is true).
    """
    app_queue = cast(Queue, MagicMock(spec=Queue))
    original = worker._queue
    try:
        worker._queue = None
        worker.create_embedded_worker(app_queue, concurrency=1)

        assert worker._get_queue() is app_queue
    finally:
        worker._queue = original
