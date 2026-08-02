"""Log-level policy for the request access log.

Scanner probes and SPA deep links all land on the static/catch-all routes. At
INFO they bury the API traffic that actually carries signal, so they are logged
at DEBUG instead — unless the request failed with a server error.
"""

import logging

SERVER_ERROR_STATUS = 500


def is_api_path(path: str, api_prefix: str) -> bool:
    """True when the path is handled by an API router rather than by static/SPA."""
    prefix = api_prefix.rstrip("/")
    return path == prefix or path.startswith(f"{prefix}/")


def access_log_level(path: str, api_prefix: str, status_code: int | None = None) -> int:
    """Level for the request_started / request_completed pair.

    ``status_code`` is None on request_started, where the outcome isn't known yet.
    """
    if status_code is not None and status_code >= SERVER_ERROR_STATUS:
        return logging.WARNING
    if is_api_path(path, api_prefix):
        return logging.INFO
    return logging.DEBUG
